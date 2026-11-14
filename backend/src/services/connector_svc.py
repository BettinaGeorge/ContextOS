import asyncio
import hashlib
import uuid
from dataclasses import dataclass, field

from sqlalchemy.ext.asyncio import AsyncSession

from src.connectors.base import NormalizedArtifact
from src.connectors.github_connector import GitHubConnector
from src.connectors.notion_connector import NotionConnector
from src.llm.voyage_client import VoyageClient
from src.models.artifact import Artifact, ArtifactType, SourceSystem
from src.models.connector import Connector
from src.repositories.artifact_repository import ArtifactRepository, ExistingPiece
from src.repositories.connector_repository import ConnectorRepository
from src.services.chunking import chunk_source_file


@dataclass
class Partition:
    new: list[Artifact] = field(default_factory=list)
    content_changed: list[Artifact] = field(default_factory=list)
    metadata_changed: list[Artifact] = field(default_factory=list)
    unchanged: list[Artifact] = field(default_factory=list)


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def partition_rows(
    rows: list[Artifact], existing: dict[tuple[ArtifactType, str], ExistingPiece]
) -> Partition:
    """Splits freshly built rows against what is already stored, so only new or
    content-changed pieces are embedded."""
    partition = Partition()
    for row in rows:
        stored = existing.get((ArtifactType(row.artifact_type), row.source_artifact_id))
        if stored is None:
            partition.new.append(row)
        elif stored.checksum != row.checksum or not stored.has_embedding:
            partition.content_changed.append(row)
        elif stored.title != row.title or stored.source_url != row.source_url:
            partition.metadata_changed.append(row)
        else:
            partition.unchanged.append(row)
    return partition


class ConnectorService:
    """Dispatches to the right connector, chunks source files (research.md
    §3), and persists the resulting artifact rows idempotently: a piece is
    identified by (workspace, source system, type, source id), embedded only
    when new or changed (checksum is the SHA-256 of its content), and updated
    in place so relationships keep pointing at it. Deterministic relationship
    extraction happens separately (relationship_svc, T038) after all of a
    workspace's artifacts exist."""

    def __init__(self, session: AsyncSession, voyage_client: VoyageClient | None = None):
        self._session = session
        self._connectors = ConnectorRepository(session)
        self._artifacts = ArtifactRepository(session)
        self._voyage = voyage_client or VoyageClient()

    async def ingest(self, workspace_id: uuid.UUID, connector: Connector) -> int:
        raw_token = await self._connectors.decrypt_for_use(connector)
        normalized = await self._fetch_normalized(connector, raw_token)
        return await self.ingest_normalized(workspace_id, connector.source_system, normalized)

    async def ingest_normalized(
        self,
        workspace_id: uuid.UUID,
        source_system: SourceSystem,
        normalized: list[NormalizedArtifact],
    ) -> int:
        rows = self._to_artifact_rows(workspace_id, source_system, normalized)
        existing = await self._artifacts.existing_pieces(workspace_id, source_system)
        plan = partition_rows(rows, existing)
        to_write = plan.new + plan.content_changed
        if to_write:
            # embed_documents blocks for real (network calls plus rate-limit
            # pacing sleeps, T062) — running it inline on the event loop
            # would freeze the whole server, not just this one job. Offload
            # to a worker thread so other requests keep being served.
            embeddings = await asyncio.to_thread(
                self._voyage.embed_documents, [r.content for r in to_write]
            )
            for row, embedding in zip(to_write, embeddings, strict=True):
                row.embedding = embedding
        source_file_ids = [n.source_artifact_id for n in normalized if n.artifact_type == "source_file"]
        try:
            await self._artifacts.upsert_content(to_write)
            await self._artifacts.update_metadata(workspace_id, plan.metadata_changed)
            await self._artifacts.delete_stale_source_file_pieces(
                workspace_id,
                source_system,
                file_ids=source_file_ids,
                current_piece_ids={r.source_artifact_id for r in rows},
            )
            await self._session.commit()
        except Exception:
            await self._session.rollback()
            raise
        return len(rows)

    async def _fetch_normalized(
        self, connector: Connector, raw_token: str
    ) -> list[NormalizedArtifact]:
        if connector.source_system == SourceSystem.github:
            owner, repo = connector.external_resource_ref.split("/", 1)
            client = GitHubConnector(access_token=raw_token, owner=owner, repo=repo)
        elif connector.source_system == SourceSystem.notion:
            page_ids = connector.external_resource_ref.split(",")
            client = NotionConnector(integration_token=raw_token, page_ids=page_ids)
        else:
            raise ValueError(f"Unsupported source_system: {connector.source_system}")

        await client.authenticate()
        return await client.ingest_full()

    def _to_artifact_rows(
        self,
        workspace_id: uuid.UUID,
        source_system: SourceSystem,
        normalized: list[NormalizedArtifact],
    ) -> list[Artifact]:
        rows: list[Artifact] = []
        for n in normalized:
            if n.artifact_type == "source_file":
                chunks = chunk_source_file(n.title, n.content)
                if len(chunks) <= 1:
                    if n.content.strip():
                        rows.append(self._artifact_from_normalized(workspace_id, source_system, n))
                    continue
                for i, chunk in enumerate(chunks):
                    if not chunk.text.strip():
                        continue
                    chunk_label = chunk.symbol_name or f"lines {chunk.start_line}-{chunk.end_line}"
                    rows.append(
                        Artifact(
                            workspace_id=workspace_id,
                            source_system=source_system,
                            source_artifact_id=f"{n.source_artifact_id}#chunk{i}",
                            artifact_type=n.artifact_type,
                            title=f"{n.title} ({chunk_label})",
                            content=chunk.text,
                            source_url=f"{n.source_url}#L{chunk.start_line}-L{chunk.end_line}",
                            checksum=_sha256(chunk.text),
                        )
                    )
            elif n.content.strip():
                rows.append(self._artifact_from_normalized(workspace_id, source_system, n))
        return rows

    def _artifact_from_normalized(
        self, workspace_id: uuid.UUID, source_system: SourceSystem, n: NormalizedArtifact
    ) -> Artifact:
        return Artifact(
            workspace_id=workspace_id,
            source_system=source_system,
            source_artifact_id=n.source_artifact_id,
            artifact_type=n.artifact_type,
            title=n.title,
            content=n.content,
            structured_content=n.structured_content,
            author=n.author,
            created_at=n.created_at,
            updated_at=n.updated_at,
            source_url=n.source_url,
            checksum=_sha256(n.content),
        )
