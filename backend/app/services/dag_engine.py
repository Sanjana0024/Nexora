from collections import defaultdict

from app.schemas.workflow import WorkflowCreate


class DAGEngine:

    def __init__(self, workflow: WorkflowCreate):
        self.workflow = workflow

    def build_graph(self):
        graph = defaultdict(list)

        for edge in self.workflow.edges:
            graph[edge.source].append(edge.target)

        return graph

    def build_in_degree(self):
        in_degree = {
            node.id: 0
            for node in self.workflow.nodes
        }

        for edge in self.workflow.edges:
            in_degree[edge.target] += 1

        return in_degree

    def get_execution_levels(self):

        graph = self.build_graph()
        in_degree = self.build_in_degree()

        levels = []

        while True:

            current_level = [
                node_id
                for node_id, degree in in_degree.items()
                if degree == 0
            ]

            if not current_level:
                break

            levels.append(current_level)

            for node_id in current_level:

                # Mark this node as processed
                in_degree[node_id] = -1

                for next_node in graph[node_id]:
                    in_degree[next_node] -= 1

        processed_nodes = sum(len(level) for level in levels)

        if processed_nodes != len(self.workflow.nodes):
            raise ValueError(
                "Workflow contains a cycle"
            )

        return levels