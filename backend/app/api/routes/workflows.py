from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.database import get_db

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
@router.get("/database-test")
def database_test(db: Session = Depends(get_db)):

    result = db.execute(
        text("SELECT current_database();")
    )

    database_name = result.scalar()

    return {
        "status": "connected",
        "database": database_name,
    }