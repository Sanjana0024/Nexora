from app.schemas.workflow import WorkflowCreate


class WorkflowValidationError(Exception):
    pass


def validate_workflow(workflow: WorkflowCreate):
    node_ids = {node.id for node in workflow.nodes}

    # Check for duplicate node IDs
    if len(node_ids) != len(workflow.nodes):
        raise WorkflowValidationError(
            "Workflow contains duplicate node IDs"
        )

    # Check that every edge references existing nodes
    for edge in workflow.edges:
        if edge.source not in node_ids:
            raise WorkflowValidationError(
                f"Source node '{edge.source}' does not exist"
            )

        if edge.target not in node_ids:
            raise WorkflowValidationError(
                f"Target node '{edge.target}' does not exist"
            )

    # A node cannot connect to itself
    for edge in workflow.edges:
        if edge.source == edge.target:
            raise WorkflowValidationError(
                f"Node '{edge.source}' cannot connect to itself"
            )

    return True