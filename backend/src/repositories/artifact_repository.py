import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.artifact import Artifact, ArtifactType


class ArtifactRepository:
    """Every query is scoped by workspace_id (Constitution Principle VI) — there
    is no method here that can return an artifact without a workspace filter."""

    def __init__(self, session: AsyncSession):
        self._session = session

    async def create(self, artifact: Artifact) -> Artifact:
        self._session.add(artifact)
        await self._session.commit()
        await self._session.refresh(artifact)
        return artifact

    async def create_many(self, artifacts: list[Artifact]) -> list[Artifact]:
        self._session.add_all(artifacts)
        await self._session.commit()
        for a in artifacts:
            await self._session.refresh(a)
        return artifacts

    async def get_by_id(self, workspace_id: uuid.UUID, artifact_id: uuid.UUID) -> Artifact | None:
        result = await self._session.execute(
            select(Artifact).where(
                Artifact.workspace_id == workspace_id, Artifact.id == artifact_id
            )
        )
        return result.scalar_one_or_none()

    async def list_by_workspace(
        self, workspace_id: uuid.UUID, artifact_type: ArtifactType | None = None
    ) -> list[Artifact]:
        query = select(Artifact).where(Artifact.workspace_id == workspace_id)
        if artifact_type is not None:
            query = query.where(Artifact.artifact_type == artifact_type)
        result = await self._session.execute(query)
        return list(result.scalars().all())

    async def search_fulltext(self, workspace_id: uuid.UUID, query_text: str) -> list[Artifact]:
        """Simple ILIKE-based full-text search over title/content — sufficient
        at this data volume (research.md §5: no special indexing needed yet)."""
        pattern = f"%{query_text}%"
        result = await self._session.execute(
            select(Artifact).where(
                Artifact.workspace_id == workspace_id,
                (Artifact.title.ilike(pattern)) | (Artifact.content.ilike(pattern)),
            )
        )
        return list(result.scalars().all())

    async def search_by_embedding(
        self, workspace_id: uuid.UUID, embedding: list[float], limit: int = 10
    ) -> list[Artifact]:
        """Cosine-distance nearest neighbors, plain column scan (research.md §5)."""
        result = await self._session.execute(
            select(Artifact)
            .where(Artifact.workspace_id == workspace_id, Artifact.embedding.isnot(None))
            .order_by(Artifact.embedding.cosine_distance(embedding))
            .limit(limit)
        )
        return list(result.scalars().all())
