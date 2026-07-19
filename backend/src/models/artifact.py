import enum
import uuid
from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.core.db import Base

# voyage-code-3 default output dimension (research.md §6). Revisit if the
# embedding model choice changes.
EMBEDDING_DIM = 1024


class SourceSystem(enum.StrEnum):
    github = "github"
    notion = "notion"


class ArtifactType(enum.StrEnum):
    source_file = "source_file"
    commit = "commit"
    pull_request = "pull_request"
    issue = "issue"
    document = "document"


class Artifact(Base):
    """A normalized representation of one ingested item (docs/prd.md §6)."""

    __tablename__ = "artifacts"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False
    )
    source_system: Mapped[SourceSystem] = mapped_column(
        Enum(SourceSystem, name="artifact_source_system"), nullable=False
    )
    source_artifact_id: Mapped[str] = mapped_column(String, nullable=False)
    artifact_type: Mapped[ArtifactType] = mapped_column(
        Enum(ArtifactType, name="artifact_type"), nullable=False
    )
    title: Mapped[str] = mapped_column(String, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    structured_content: Mapped[dict | None] = mapped_column(JSONB)
    author: Mapped[str | None] = mapped_column(String)
    created_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # Every citation needs an openable link (FR-010) — never nullable.
    source_url: Mapped[str] = mapped_column(String, nullable=False)
    parent_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("artifacts.id", ondelete="CASCADE")
    )
    checksum: Mapped[str | None] = mapped_column(String)
    ingestion_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    embedding: Mapped[list[float] | None] = mapped_column(Vector(EMBEDDING_DIM))
    ingested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
