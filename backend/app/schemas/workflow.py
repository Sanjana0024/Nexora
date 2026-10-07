from typing import Any

from pydantic import BaseModel, Field


class WorkflowNode(BaseModel):
    id: str
    type: str
    name: str
    config: dict[str, Any] = Field(default_factory=dict)
    retry_count: int = Field(default=0, ge=0, le=5)


class WorkflowEdge(BaseModel):
    source: str
    target: str
    condition: str | None = None


class WorkflowCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    description: str = Field(min_length=1, max_length=500)
    nodes: list[WorkflowNode]
    edges: list[WorkflowEdge]