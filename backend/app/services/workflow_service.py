from sqlalchemy.orm import Session

from app.models.workflow import Workflow


class WorkflowService:

    def __init__(self, db: Session):
        self.db = db

    def create_workflow(
        self,
        name: str,
        description: str,
    ):

        workflow = Workflow(
            name=name,
            description=description,
        )

        self.db.add(workflow)
        self.db.commit()
        self.db.refresh(workflow)

        return workflow