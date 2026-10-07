import asyncio

from app.services.node_runtime import NodeRuntime
from app.services.retry_handler import RetryHandler
from app.models.workflow_run import WorkflowRun


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
        self.run = WorkflowRun(
        workflow.name
    )

        self.node_outputs = {}

        self.dependencies = {
            node.id: []
            for node in workflow.nodes
        }

        self.active_nodes = set()

        self.skipped_nodes = set()

        self.build_dependencies()

    def build_dependencies(self):

        for edge in self.workflow.edges:

            self.dependencies[edge.target].append(
                edge.source
            )

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

            # Normal edge
            if edge.condition is None:

                active_targets.append(
                    edge.target
                )

                continue

            # Conditional edge
            result = None

            if isinstance(node_output, dict):

                result = node_output.get(
                    "result"
                )

            if (
                edge.condition == "true"
                and result is True
            ):
                active_targets.append(
                    edge.target
                )

            elif (
                edge.condition == "false"
                and result is False
            ):
                active_targets.append(
                    edge.target
                )

        return active_targets

    def get_skipped_targets(
        self,
        node_id,
        node_output
    ):

        active_targets = set(
            self.get_active_targets(
                node_id,
                node_output
            )
        )

        skipped_targets = set()

        for edge in self.get_outgoing_edges(node_id):

            if edge.target not in active_targets:

                skipped_targets.add(
                    edge.target
                )

        return skipped_targets

    async def execute_node(self, node_id):

        node = self.nodes[node_id]

        input_data = self.get_node_input(
            node_id
        )

        print(
            f"Starting node: {node.name}"
        )

        print(
            f"Input: {input_data}"
        )

        async def run_node():

            return await self.runtime.execute(
                node,
                input_data
            )

        execution = await self.retry_handler.execute_with_retry(
            run_node,
            node.retry_count
        )

        if execution["success"]:

            result = execution["result"]

            self.node_outputs[node_id] = result

            print(
                f"Completed node: {node.name}"
            )

            return {
                "node_id": node.id,
                "node_name": node.name,
                "input": input_data,
                "output": result,
                "status": "completed",
                "attempts": execution["attempts"],
            }

        print(
            f"Node failed permanently: {node.name}"
        )

        return {
            "node_id": node.id,
            "node_name": node.name,
            "input": input_data,
            "output": None,
            "status": "failed",
            "attempts": execution["attempts"],
            "error": execution["error"],
        }

    async def execute(self):

        results = []

        for level in self.execution_levels:

            runnable_nodes = []

            for node_id in level:

                if node_id in self.skipped_nodes:

                    continue

                runnable_nodes.append(
                    node_id
                )

            if not runnable_nodes:

                continue

            level_results = await asyncio.gather(
                *[
                    self.execute_node(node_id)
                    for node_id in runnable_nodes
                ]
            )

            results.extend(
                level_results
            )

            # Determine branches after execution
            for result in level_results:

                node_id = result["node_id"]

                node_output = result["output"]

                active_targets = (
                    self.get_active_targets(
                        node_id,
                        node_output
                    )
                )

                skipped_targets = (
                    self.get_skipped_targets(
                        node_id,
                        node_output
                    )
                )

                self.active_nodes.update(
                    active_targets
                )

                self.skipped_nodes.update(
                    skipped_targets
                )

        return results