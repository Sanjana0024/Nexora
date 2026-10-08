from uuid import uuid4

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.base import Base


class WorkflowEdge(Base):

    __tablename__ = "workflow_edges"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid4()),
    )

    workflow_id: Mapped[str] = mapped_column(
        ForeignKey("workflows.id", ondelete="CASCADE"),
        nullable=False,
    )

    source_node_id: Mapped[str] = mapped_column(
        ForeignKey("workflow_nodes.id", ondelete="CASCADE"),
        nullable=False,
    )

    target_node_id: Mapped[str] = mapped_column(
        ForeignKey("workflow_nodes.id", ondelete="CASCADE"),
        nullable=False,
    )

    condition: Mapped[str | None] = mapped_column(
        String(20),
        nullable=True,
    )