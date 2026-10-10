from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.workflow import Workflow
from app.models.workflow_node import WorkflowNode
from app.models.workflow_edge import WorkflowEdge
from app.schemas.workflow import WorkflowCreate

from app.services.workflow_validator import (
    validate_workflow,
    WorkflowValidationError,
)
from app.schemas.workflow import (
    WorkflowCreate,
    WorkflowNode as WorkflowNodeSchema,
    WorkflowEdge as WorkflowEdgeSchema,
)

from app.services.dag_engine import DAGEngine
from app.services.workflow_executor import WorkflowExecutor


router = APIRouter(
    prefix="/workflows",
    tags=["Workflows"],
)


@router.post("/")
def create_workflow(
    workflow: WorkflowCreate,
    db: Session = Depends(get_db),
):

    try:
        # 1. Validate workflow
        validate_workflow(workflow)

        # 2. Create workflow
        db_workflow = Workflow(
            name=workflow.name,
            description=workflow.description,
        )

        db.add(db_workflow)
        db.flush()

        # 3. Create nodes
        node_id_map = {}

        for node in workflow.nodes:

            db_node = WorkflowNode(
                workflow_id=db_workflow.id,
                node_key=node.id,
                type=node.type,
                name=node.name,
                config=node.config,
                retry_count=node.retry_count,
            )

            db.add(db_node)

            node_id_map[node.id] = db_node

        db.flush()

        # 4. Create edges
        for edge in workflow.edges:

            db_edge = WorkflowEdge(
                workflow_id=db_workflow.id,
                source_node_id=node_id_map[edge.source].id,
                target_node_id=node_id_map[edge.target].id,
                condition=edge.condition,
            )

            db.add(db_edge)

        # 5. Save everything
        db.commit()
        db.refresh(db_workflow)

        return {
            "message": "Workflow created successfully",
            "workflow_id": db_workflow.id,
            "name": db_workflow.name,
            "status": db_workflow.status,
        }

    except WorkflowValidationError as error:

        db.rollback()

        raise HTTPException(
            status_code=400,
            detail=str(error),
        )

    except Exception as error:

        db.rollback()

        raise HTTPException(
            status_code=500,
            detail=str(error),
        )


@router.get("/database-test")
def database_test(
    db: Session = Depends(get_db),
):

    from sqlalchemy import text

    result = db.execute(
        text("SELECT current_database();")
    )

    database_name = result.scalar()

    return {
        "status": "connected",
        "database": database_name,
    }

@router.get("/{workflow_id}")
def get_workflow(
    workflow_id: str,
    db: Session = Depends(get_db),
):
    workflow = (
        db.query(Workflow)
        .filter(Workflow.id == workflow_id)
        .first()
    )

    if not workflow:
        raise HTTPException(
            status_code=404,
            detail="Workflow not found",
        )

    nodes = (
        db.query(WorkflowNode)
        .filter(WorkflowNode.workflow_id == workflow.id)
        .all()
    )

    edges = (
        db.query(WorkflowEdge)
        .filter(WorkflowEdge.workflow_id == workflow.id)
        .all()
    )

    return {
        "workflow": {
            "id": workflow.id,
            "name": workflow.name,
            "description": workflow.description,
            "status": workflow.status,
            "created_at": workflow.created_at,
            "updated_at": workflow.updated_at,
        },
        "nodes": [
            {
                "id": node.id,
                "node_key": node.node_key,
                "type": node.type,
                "name": node.name,
                "config": node.config,
                "retry_count": node.retry_count,
            }
            for node in nodes
        ],
        "edges": [
            {
                "id": edge.id,
                "source_node_id": edge.source_node_id,
                "target_node_id": edge.target_node_id,
                "condition": edge.condition,
            }
            for edge in edges
        ],
    }

@router.post("/{workflow_id}/runs")
async def execute_saved_workflow(
    workflow_id: str,
    db: Session = Depends(get_db),
):
    # 1. Find the saved workflow
    db_workflow = (
        db.query(Workflow)
        .filter(Workflow.id == workflow_id)
        .first()
    )

    if db_workflow is None:
        raise HTTPException(
            status_code=404,
            detail="Workflow not found",
        )

    # 2. Load its nodes and edges from PostgreSQL
    db_nodes = (
        db.query(WorkflowNode)
        .filter(
            WorkflowNode.workflow_id == db_workflow.id
        )
        .all()
    )

    db_edges = (
        db.query(WorkflowEdge)
        .filter(
            WorkflowEdge.workflow_id == db_workflow.id
        )
        .all()
    )

    # Map database node IDs to the original workflow node keys
    nodes_by_db_id = {
        node.id: node for node in db_nodes
    }

    # 3. Reconstruct the workflow in the format
    #    expected by the existing engine
    workflow_data = WorkflowCreate(
        name=db_workflow.name,
        description=db_workflow.description,
        nodes=[
            WorkflowNodeSchema(
                id=node.node_key,
                type=node.type,
                name=node.name,
                config=node.config,
                retry_count=node.retry_count,
            )
            for node in db_nodes
        ],
        edges=[
            WorkflowEdgeSchema(
                source=nodes_by_db_id[edge.source_node_id].node_key,
                target=nodes_by_db_id[edge.target_node_id].node_key,
                condition=edge.condition,
            )
            for edge in db_edges
        ],
    )

    # 4. Validate and rebuild the DAG
    try:
        validate_workflow(workflow_data)

        dag = DAGEngine(workflow_data)
        execution_levels = dag.get_execution_levels()

    except (WorkflowValidationError, ValueError) as error:
        raise HTTPException(
            status_code=400,
            detail=str(error),
        ) from error

    # 5. Execute the workflow
    executor = WorkflowExecutor(
        workflow_data,
        execution_levels,
    )

    execution_result = await executor.execute()

    # 6. Return the result
    return {
        "message": "Workflow execution finished",
        "workflow_id": db_workflow.id,
        "execution_levels": execution_levels,
        "execution": execution_result,
    }
