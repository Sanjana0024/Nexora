
import asyncio

from app.services.node_runtime import NodeRuntime
from app.services.retry_handler import RetryHandler
from app.services.workflow_run_state import WorkflowRunState


class WorkflowExecutor:

    def __init__(self, workflow, execution_levels):
        self.workflow = workflow
        self.execution_levels = execution_levels

        self.nodes = {
            node.id: node
            for node in workflow.nodes
        }

        self.runtime = NodeRuntime()
        self.retry_handler = RetryHandler()
        self.run = WorkflowRunState(workflow.name)

        self.node_outputs = {}

        self.dependencies = {
            node.id: []
            for node in workflow.nodes
        }

        self.active_nodes = set()
        self.skipped_nodes = set()
        self.recorded_skipped_nodes = set()

        self.build_dependencies()

    def build_dependencies(self):
        for edge in self.workflow.edges:
            self.dependencies[edge.target].append(edge.source)

    def get_node_input(self, node_id):
        parent_nodes = self.dependencies[node_id]

        if not parent_nodes:
            return None

        return {
            parent_id: self.node_outputs[parent_id]
            for parent_id in parent_nodes
            if parent_id in self.node_outputs
        }

    def get_outgoing_edges(self, node_id):
        return [
            edge
            for edge in self.workflow.edges
            if edge.source == node_id
        ]

    def get_active_targets(self, node_id, node_output):
        active_targets = []

        for edge in self.get_outgoing_edges(node_id):

            # An unconditional edge is always active.
            if edge.condition is None:
                active_targets.append(edge.target)
                continue

            # Conditional edges use the condition node's result.
            result = None

            if isinstance(node_output, dict):
                result = node_output.get("result")

            if edge.condition == "true" and result is True:
                active_targets.append(edge.target)

            elif edge.condition == "false" and result is False:
                active_targets.append(edge.target)

        return active_targets

    def get_skipped_targets(self, node_id, node_output):
        active_targets = set(
            self.get_active_targets(node_id, node_output)
        )

        return {
            edge.target
            for edge in self.get_outgoing_edges(node_id)
            if edge.condition is not None
            and edge.target not in active_targets
        }

    async def execute_node(self, node_id):
        node = self.nodes[node_id]
        input_data = self.get_node_input(node_id)

        print(f"Starting node: {node.name}")
        print(f"Input: {input_data}")

        async def run_node():
            return await self.runtime.execute(node, input_data)

        execution = await self.retry_handler.execute_with_retry(
            run_node,
            node.retry_count,
        )

        if execution["success"]:
            result = execution["result"]
            self.node_outputs[node_id] = result

            print(f"Completed node: {node.name}")

            return {
                "node_id": node.id,
                "node_name": node.name,
                "input": input_data,
                "output": result,
                "status": "completed",
                "attempts": execution["attempts"],
            }

        print(f"Node failed permanently: {node.name}")

        return {
            "node_id": node.id,
            "node_name": node.name,
            "input": input_data,
            "output": None,
            "status": "failed",
            "attempts": execution["attempts"],
            "error": execution["error"],
        }

    def make_skipped_result(self, node_id):
        node = self.nodes[node_id]

        return {
            "node_id": node.id,
            "node_name": node.name,
            "input": self.get_node_input(node_id),
            "output": None,
            "status": "skipped",
            "attempts": 0,
        }

    async def execute(self):
        results = []

        try:
            for level in self.execution_levels:

                runnable_nodes = [
                    node_id
                    for node_id in level
                    if node_id not in self.skipped_nodes
                ]

                # Run eligible nodes in parallel within this DAG level.
                if runnable_nodes:
                    level_results = await asyncio.gather(
                        *[
                            self.execute_node(node_id)
                            for node_id in runnable_nodes
                        ]
                    )

                    results.extend(level_results)
                    self.run.node_results.extend(level_results)

                    for result in level_results:
                        if result["status"] == "failed":
                            self.run.mark_failed()

                            # Record any skipped nodes in this level too.
                            self.record_skipped_for_level(
                                level, results
                            )

                            return {
                                "run_id": self.run.run_id,
                                "workflow": self.run.workflow_name,
                                "status": self.run.status,
                                "results": results,
                            }

                    # First collect every selected branch.
                    for result in level_results:
                        node_id = result["node_id"]
                        node_output = result["output"]

                        self.active_nodes.update(
                            self.get_active_targets(
                                node_id, node_output
                            )
                        )

                    # Then collect inactive conditional branches.
                    for result in level_results:
                        node_id = result["node_id"]
                        node_output = result["output"]

                        self.skipped_nodes.update(
                            self.get_skipped_targets(
                                node_id, node_output
                            )
                        )

                    # A target selected by another incoming path
                    # must not remain marked as skipped.
                    self.skipped_nodes.difference_update(
                        self.active_nodes
                    )

                # Record skipped nodes instead of silently omitting them.
                self.record_skipped_for_level(level, results)

            self.run.mark_success()

            return {
                "run_id": self.run.run_id,
                "workflow": self.run.workflow_name,
                "status": self.run.status,
                "started_at": self.run.started_at,
                "completed_at": self.run.completed_at,
                "results": results,
            }

        except Exception:
            self.run.mark_failed()
            raise

    def record_skipped_for_level(self, level, results):
        for node_id in level:
            if (
                node_id in self.skipped_nodes
                and node_id not in self.recorded_skipped_nodes
            ):
                skipped_result = self.make_skipped_result(node_id)

                results.append(skipped_result)
                self.run.node_results.append(skipped_result)

                self.recorded_skipped_nodes.add(node_id)

                print(
                    f"Skipped node: {self.nodes[node_id].name}"
                )
