from fastapi import APIRouter, HTTPException

from app.schemas.workflow import WorkflowCreate

from app.services.workflow_validator import (
    validate_workflow,
    WorkflowValidationError,
)

from app.services.dag_engine import DAGEngine
from app.services.workflow_executor import WorkflowExecutor


router = APIRouter(
    prefix="/workflows",
    tags=["Workflows"],
)


@router.post("/")
async def create_workflow(workflow: WorkflowCreate):

    try:
        validate_workflow(workflow)

        dag = DAGEngine(workflow)

        execution_levels = dag.get_execution_levels()

        executor = WorkflowExecutor(
            workflow,
            execution_levels,
        )

        execution_results = await executor.execute()

    except WorkflowValidationError as error:
        raise HTTPException(
            status_code=400,
            detail=str(error),
        )

    except ValueError as error:
        raise HTTPException(
            status_code=400,
            detail=str(error),
        )

    return {
        "message": "Workflow executed successfully",
        "execution_levels": execution_levels,
        "execution_results": execution_results,
        "workflow": workflow,
    }