import asyncio
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from src.connectors.base import NormalizedArtifact
from src.connectors.github_connector import GitHubConnector
from src.connectors.notion_connector import NotionConnector
from src.llm.voyage_client import VoyageClient
from src.models.artifact import Artifact, SourceSystem
from src.models.connector import Connector
from src.repositories.artifact_repository import ArtifactRepository
from src.repositories.connector_repository import ConnectorRepository
from src.services.chunking import chunk_source_file


class ConnectorService:
    """Dispatches to the right connector, chunks source files (research.md
    §3), embeds everything via Voyage, and persists the resulting artifact
    rows. Deterministic relationship extraction happens separately
    (relationship_svc, T038) after all of a workspace's artifacts exist."""

    def __init__(self, session: AsyncSession, voyage_client: VoyageClient | None = None):
        self._session = session
        self._connectors = ConnectorRepository(session)
        self._artifacts = ArtifactRepository(session)
        self._voyage = voyage_client or VoyageClient()

    async def ingest(self, workspace_id: uuid.UUID, connector: Connector) -> int:
        raw_token = await self._connectors.decrypt_for_use(connector)
        normalized = await self._fetch_normalized(connector, raw_token)
        rows = self._to_artifact_rows(workspace_id, connector.source_system, normalized)
        if rows:
            # embed_documents blocks for real (network calls plus rate-limit
            # pacing sleeps, T062) — running it inline on the event loop
            # would freeze the whole server, not just this one job. Offload
            # to a worker thread so other requests keep being served.
            embeddings = await asyncio.to_thread(
                self._voyage.embed_documents, [r.content for r in rows]
            )
            for row, embedding in zip(rows, embeddings, strict=True):
                row.embedding = embedding
            await self._artifacts.create_many(rows)
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
                            checksum=n.checksum,
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
            checksum=n.checksum,
        )
