from app.core.base import Base
from app.core.database import engine

from app.models import (
    Workflow,
    WorkflowNode,
    WorkflowEdge,
    WorkflowRun,
    NodeRun,init
)


def init_db():
    Base.metadata.create_all(bind=engine)