import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from src.llm.voyage_client import VoyageClient
from src.models.artifact import Artifact
from src.repositories.artifact_repository import ArtifactRepository

DEFAULT_LIMIT = 10


class RetrievalService:
    """Full-text + vector similarity search (PRD §4) — no graph traversal,
    no reranking model, no special vector index (research.md §5), all
    deliberately deferred past Phase 1."""

    def __init__(self, session: AsyncSession, voyage_client: VoyageClient | None = None):
        self._artifacts = ArtifactRepository(session)
        self._voyage = voyage_client or VoyageClient()

    async def retrieve(
        self, workspace_id: uuid.UUID, query_text: str, limit: int = DEFAULT_LIMIT
    ) -> list[Artifact]:
        fulltext_hits = await self._artifacts.search_fulltext(workspace_id, query_text)
        query_embedding = self._voyage.embed_query(query_text)
        vector_hits = await self._artifacts.search_by_embedding(
            workspace_id, query_embedding, limit=limit
        )

        # Full-text hits first — an exact keyword/phrase match is a stronger
        # relevance signal than embedding-space proximity at this scale.
        seen: set[uuid.UUID] = set()
        merged: list[Artifact] = []
        for artifact in fulltext_hits + vector_hits:
            if artifact.id not in seen:
                seen.add(artifact.id)
                merged.append(artifact)
        return merged[:limit]
