import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.core.db import Base


class SourceSystem(enum.StrEnum):
    github = "github"
    notion = "notion"


class ConnectorStatus(enum.StrEnum):
    connected = "connected"
    ingesting = "ingesting"
    complete = "complete"
    failed = "failed"
    needs_reconnect = "needs_reconnect"


class Connector(Base):
    """A connection to GitHub or Notion, scoped to one workspace.

    T020: encrypted_access_token is written/read exclusively through
    connector_repository, which encrypts before every write and decrypts
    only at point of use (FR-016, Constitution Principle III). The column
    itself is just opaque ciphertext — never assume it's readable here.
    """

    __tablename__ = "connectors"
    __table_args__ = (
        UniqueConstraint("workspace_id", "source_system", name="uq_connector_workspace_source"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False
    )
    source_system: Mapped[SourceSystem] = mapped_column(
        Enum(SourceSystem, name="source_system"), nullable=False
    )
    status: Mapped[ConnectorStatus] = mapped_column(
        Enum(ConnectorStatus, name="connector_status"),
        nullable=False,
        default=ConnectorStatus.connected,
    )
    encrypted_access_token: Mapped[str] = mapped_column(String, nullable=False)
    external_resource_ref: Mapped[str] = mapped_column(String, nullable=False)
    last_ingested_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error_message: Mapped[str | None] = mapped_column(String)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
