import enum
import uuid
from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.core.db import Base


class RelationshipOrigin(enum.StrEnum):
    explicit = "explicit"
    metadata_derived = "metadata-derived"
    model_inferred = "model-inferred"
    user_confirmed = "user-confirmed"


# Phase 1 code paths only ever write these two origins (research.md §4).
# model_inferred/user_confirmed exist in the schema for forward compatibility
# per docs/prd.md §6, but nothing in this phase produces them.
PHASE_1_ALLOWED_ORIGINS = (RelationshipOrigin.explicit, RelationshipOrigin.metadata_derived)


class Relationship(Base):
    """A directed link between two artifacts (docs/prd.md §6).

    The DB-level check constraint below is a deliberate belt-and-suspenders
    guard for Constitution Principle II: even if application code has a bug,
    the database itself refuses to store a Phase-1-written relationship with
    an origin other than explicit/metadata-derived.
    """

    __tablename__ = "relationships"
    __table_args__ = (
        CheckConstraint(
            "relationship_origin IN ('explicit', 'metadata-derived', 'model-inferred', "
            "'user-confirmed')",
            name="ck_relationship_origin_valid",
        ),
        UniqueConstraint(
            "workspace_id",
            "source_artifact_id",
            "target_artifact_id",
            "relationship_type",
            name="uq_relationship_edge",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False
    )
    source_artifact_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("artifacts.id", ondelete="CASCADE"), nullable=False
    )
    target_artifact_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("artifacts.id", ondelete="CASCADE"), nullable=False
    )
    relationship_type: Mapped[str] = mapped_column(String, nullable=False)
    relationship_origin: Mapped[RelationshipOrigin] = mapped_column(
        Enum(
            RelationshipOrigin,
            name="relationship_origin",
            values_callable=lambda e: [i.value for i in e],
        ),
        nullable=False,
    )
    confidence: Mapped[float | None] = mapped_column(Float)
    evidence: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
