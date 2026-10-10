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
from datetime import datetime, timezone

from app.models.workflow_run import WorkflowRun
from app.models.node_run import NodeRun
from app.services.ai_planner import plan_workflow


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

    db_nodes = (
        db.query(WorkflowNode)
        .filter(WorkflowNode.workflow_id == db_workflow.id)
        .all()
    )

    db_edges = (
        db.query(WorkflowEdge)
        .filter(WorkflowEdge.workflow_id == db_workflow.id)
        .all()
    )

    nodes_by_db_id = {node.id: node for node in db_nodes}

    try:
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

        validate_workflow(workflow_data)

        dag = DAGEngine(workflow_data)
        execution_levels = dag.get_execution_levels()

    except (WorkflowValidationError, ValueError, KeyError) as error:
        raise HTTPException(
            status_code=400,
            detail=str(error),
        ) from error

    # 1. Create a persistent run record before execution.
    started_at = datetime.now(timezone.utc)

    db_run = WorkflowRun(
        workflow_id=db_workflow.id,
        status="RUNNING",
        started_at=started_at,
        completed_at=None,
    )

    try:
        db.add(db_run)
        db.commit()
        db.refresh(db_run)
    except Exception as error:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail="Could not create workflow run record",
        ) from error

    # Map workflow node keys to their database UUIDs.
    node_key_to_db_id = {
        node.node_key: node.id for node in db_nodes
    }

    # 2. Execute the workflow.
    executor = WorkflowExecutor(workflow_data, execution_levels)

    try:
        execution_result = await executor.execute()

        completed_at = datetime.now(timezone.utc)
        final_status = execution_result.get("status", "FAILED")

        # 3. Save the final status and completion time.
        db_run.status = final_status
        db_run.completed_at = completed_at

        # 4. Persist every node result returned by the executor.
        for result in execution_result.get("results", []):
            node_key = result["node_id"]
            database_node_id = node_key_to_db_id.get(node_key)

            if database_node_id is None:
                raise ValueError(
                    f"No database node found for '{node_key}'"
                )

            db_node_run = NodeRun(
                workflow_run_id=db_run.id,
                node_id=database_node_id,
                status=result.get("status", "completed"),
                input_data=result.get("input"),
                output_data=result.get("output"),
                error=result.get("error"),
                attempts=result.get("attempts", 1),
                started_at=started_at,
                completed_at=completed_at,
            )

            db.add(db_node_run)

        db.commit()
        db.refresh(db_run)

        # Use the persistent database run ID in the response.
        execution_result["run_id"] = db_run.id
        execution_result["status"] = db_run.status
        execution_result["started_at"] = db_run.started_at.isoformat()
        execution_result["completed_at"] = (
            db_run.completed_at.isoformat()
            if db_run.completed_at
            else None
        )

        return {
            "message": "Workflow execution finished",
            "workflow_id": db_workflow.id,
            "execution_levels": execution_levels,
            "execution": execution_result,
        }

    except Exception as error:
        db.rollback()

        # Keep a failed run in the database for later inspection.
        db_run.status = "FAILED"
        db_run.completed_at = datetime.now(timezone.utc)

        try:
            db.commit()
        except Exception:
            db.rollback()

        raise HTTPException(
            status_code=500,
            detail="Workflow execution or result persistence failed",
        ) from error

@router.get("/{workflow_id}/runs")
def get_workflow_runs(
    workflow_id: str,
    db: Session = Depends(get_db),
):
    # Confirm that the workflow exists.
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

    # Fetch previous runs, newest first.
    runs = (
        db.query(WorkflowRun)
        .filter(WorkflowRun.workflow_id == workflow_id)
        .order_by(WorkflowRun.started_at.desc())
        .all()
    )

    return {
        "workflow_id": workflow_id,
        "total_runs": len(runs),
        "runs": [
            {
                "run_id": run.id,
                "status": run.status,
                "started_at": (
                    run.started_at.isoformat()
                    if run.started_at else None
                ),
                "completed_at": (
                    run.completed_at.isoformat()
                    if run.completed_at else None
                ),
            }
            for run in runs
        ],
    }


@router.get("/{workflow_id}/runs/{run_id}")
def get_workflow_run_details(
    workflow_id: str,
    run_id: str,
    db: Session = Depends(get_db),
):
    # Confirm that the workflow exists.
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

    # Find this run under the specified workflow.
    db_run = (
        db.query(WorkflowRun)
        .filter(
            WorkflowRun.id == run_id,
            WorkflowRun.workflow_id == workflow_id,
        )
        .first()
    )

    if db_run is None:
        raise HTTPException(
            status_code=404,
            detail="Workflow run not found",
        )

    # Get all node results for this run.
    node_runs = (
        db.query(NodeRun)
        .filter(NodeRun.workflow_run_id == db_run.id)
        .order_by(NodeRun.started_at.asc())
        .all()
    )

    # Fetch node names and readable node keys.
    node_ids = [item.node_id for item in node_runs]

    db_nodes = (
        db.query(WorkflowNode)
        .filter(WorkflowNode.id.in_(node_ids))
        .all()
        if node_ids else []
    )

    nodes_by_id = {
        node.id: node for node in db_nodes
    }

    return {
        "workflow_id": workflow_id,
        "workflow_name": db_workflow.name,
        "run": {
            "run_id": db_run.id,
            "status": db_run.status,
            "started_at": (
                db_run.started_at.isoformat()
                if db_run.started_at else None
            ),
            "completed_at": (
                db_run.completed_at.isoformat()
                if db_run.completed_at else None
            ),
            "nodes": [
                {
                    "node_id": item.node_id,
                    "node_key": (
                        nodes_by_id[item.node_id].node_key
                        if item.node_id in nodes_by_id else None
                    ),
                    "node_name": (
                        nodes_by_id[item.node_id].name
                        if item.node_id in nodes_by_id else None
                    ),
                    "status": item.status,
                    "attempts": item.attempts,
                    "input": item.input_data,
                    "output": item.output_data,
                    "error": item.error,
                    "started_at": (
                        item.started_at.isoformat()
                        if item.started_at else None
                    ),
                    "completed_at": (
                        item.completed_at.isoformat()
                        if item.completed_at else None
                    ),
                }
                for item in node_runs
            ],
        },
    }

@router.post("/plan")
def plan_workflow_endpoint(
    request: dict,
):
    user_request = request.get("prompt", "").strip()

    if not user_request:
        raise HTTPException(
            status_code=400,
            detail="Please provide a workflow prompt.",
        )

    if len(user_request) > 5000:
        raise HTTPException(
            status_code=400,
            detail="Prompt must be 5000 characters or fewer.",
        )

    try:
        workflow = plan_workflow(user_request)

        return {
            "message": "Workflow planned successfully",
            "workflow": workflow.model_dump(),
        }

    except Exception as error:
        # Keep internal API keys and provider details out of the response.
        print(f"Workflow planning failed: {error}")

        raise HTTPException(
            status_code=502,
            detail="AI workflow planning failed. Check the backend terminal.",
        ) from error

@router.post("/plan-and-save")
def plan_and_save_workflow(
    request: dict,
    db: Session = Depends(get_db),
):
    user_request = request.get("prompt", "").strip()

    if not user_request:
        raise HTTPException(
            status_code=400,
            detail="Please provide a workflow prompt.",
        )

    if len(user_request) > 5000:
        raise HTTPException(
            status_code=400,
            detail="Prompt must be 5000 characters or fewer.",
        )

    try:
        # 1. Generate and validate the workflow with Gemini.
        workflow = plan_workflow(user_request)

        # 2. Save the generated workflow and its nodes.
        db_workflow = Workflow(
            name=workflow.name,
            description=workflow.description,
        )
        db.add(db_workflow)
        db.flush()

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

        # 3. Save the connections between nodes.
        for edge in workflow.edges:
            db_edge = WorkflowEdge(
                workflow_id=db_workflow.id,
                source_node_id=node_id_map[edge.source].id,
                target_node_id=node_id_map[edge.target].id,
                condition=edge.condition,
            )
            db.add(db_edge)

        db.commit()
        db.refresh(db_workflow)

        return {
            "message": "AI workflow generated and saved successfully",
            "workflow_id": db_workflow.id,
            "name": db_workflow.name,
            "node_count": len(workflow.nodes),
            "edge_count": len(workflow.edges),
            "workflow": workflow.model_dump(),
        }

    except Exception as error:
        db.rollback()
        print(f"Plan-and-save failed: {error}")

        raise HTTPException(
            status_code=502,
            detail="Workflow generation or saving failed. Check the backend terminal.",
        ) from error
