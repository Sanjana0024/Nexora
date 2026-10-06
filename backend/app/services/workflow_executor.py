import asyncio

from app.services.node_runtime import NodeRuntime


class WorkflowExecutor:

    def __init__(self, workflow, execution_levels):

        self.workflow = workflow
        self.execution_levels = execution_levels

        self.nodes = {
            node.id: node
            for node in workflow.nodes
        }

        self.runtime = NodeRuntime()

        # Stores the output produced by every node
        self.node_outputs = {}

        # Stores which nodes are parents of each node
        self.dependencies = {
            node.id: []
            for node in workflow.nodes
        }

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

        parent_outputs = {
            parent_id: self.node_outputs[parent_id]
            for parent_id in parent_nodes
        }

        return parent_outputs

    async def execute_node(self, node_id):

        node = self.nodes[node_id]

        input_data = self.get_node_input(node_id)

        print(f"Starting node: {node.name}")
        print(f"Input: {input_data}")

        result = await self.runtime.execute(
            node,
            input_data,
        )

        self.node_outputs[node_id] = result

        print(f"Completed node: {node.name}")

        return {
            "node_id": node.id,
            "node_name": node.name,
            "input": input_data,
            "output": result,
        }

    async def execute(self):

        results = []

        for level in self.execution_levels:

            print(f"Executing level: {level}")

            level_results = await asyncio.gather(
                *[
                    self.execute_node(node_id)
                    for node_id in level
                ]
            )

            results.extend(level_results)

        return results
def get_active_targets(self, node_id, node_output):

    targets = []

    for edge in self.workflow.edges:

        if edge.source != node_id:
            continue

        if edge.condition is None:
            targets.append(edge.target)
            continue

        if (
            isinstance(node_output, dict)
            and node_output.get("result") is True
            and edge.condition == "true"
        ):
            targets.append(edge.target)

        elif (
            isinstance(node_output, dict)
            and node_output.get("result") is False
            and edge.condition == "false"
        ):
            targets.append(edge.target)

            return targets