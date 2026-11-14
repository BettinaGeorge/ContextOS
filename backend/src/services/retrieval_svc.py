import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from src.llm.voyage_client import VoyageClient
from src.models.artifact import Artifact
from src.repositories.artifact_repository import ArtifactRepository

DEFAULT_LIMIT = 10
RRF_K = 60


def reciprocal_rank_fusion(*ranked_lists: list, limit: int) -> list:
    """Merges ranked lists: each appearance adds 1 / (RRF_K + rank) to an item's score, so
    an item ranked well by both keyword and vector search beats one ranked well by only
    one. Ties keep input order."""
    scores: dict = {}
    items: dict = {}
    for ranked in ranked_lists:
        for rank, item in enumerate(ranked, start=1):
            items.setdefault(item.id, item)
            scores[item.id] = scores.get(item.id, 0.0) + 1.0 / (RRF_K + rank)
    ordered = sorted(items, key=lambda item_id: scores[item_id], reverse=True)
    return [items[item_id] for item_id in ordered[:limit]]


class RetrievalService:
    """Ranked keyword search + vector similarity search (PRD §4), merged by reciprocal
    rank fusion (ADR-006) — no graph traversal, no reranking model, no special vector
    index (research.md §5), all deliberately deferred past Phase 1."""

    def __init__(self, session: AsyncSession, voyage_client: VoyageClient | None = None):
        self._artifacts = ArtifactRepository(session)
        self._voyage = voyage_client or VoyageClient()

    async def retrieve(
        self, workspace_id: uuid.UUID, query_text: str, limit: int = DEFAULT_LIMIT
    ) -> list[Artifact]:
        keyword_hits = await self._artifacts.search_fulltext(
            workspace_id, query_text, limit=limit
        )
        query_embedding = self._voyage.embed_query(query_text)
        vector_hits = await self._artifacts.search_by_embedding(
            workspace_id, query_embedding, limit=limit
        )
        return reciprocal_rank_fusion(keyword_hits, vector_hits, limit=limit)
