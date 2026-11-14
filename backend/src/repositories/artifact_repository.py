import uuid
from dataclasses import dataclass

from sqlalchemy import delete, func, or_, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.artifact import Artifact, ArtifactType, SourceSystem


@dataclass(frozen=True)
class ExistingPiece:
    """What ingestion needs to know about a stored piece to decide whether it changed."""

    checksum: str | None
    title: str
    source_url: str
    has_embedding: bool


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

    async def existing_pieces(
        self, workspace_id: uuid.UUID, source_system: SourceSystem
    ) -> dict[tuple[ArtifactType, str], ExistingPiece]:
        result = await self._session.execute(
            select(
                Artifact.artifact_type,
                Artifact.source_artifact_id,
                Artifact.checksum,
                Artifact.title,
                Artifact.source_url,
                Artifact.embedding.isnot(None).label("has_embedding"),
            ).where(
                Artifact.workspace_id == workspace_id, Artifact.source_system == source_system
            )
        )
        return {
            (row.artifact_type, row.source_artifact_id): ExistingPiece(
                checksum=row.checksum,
                title=row.title,
                source_url=row.source_url,
                has_embedding=row.has_embedding,
            )
            for row in result.all()
        }

    async def upsert_content(self, rows: list[Artifact]) -> None:
        """Inserts new pieces and rewrites changed ones in place, so the row id (and every
        relationship pointing at it) survives re-ingestion. Does not commit."""
        for row in rows:
            statement = pg_insert(Artifact).values(
                id=uuid.uuid4(),
                workspace_id=row.workspace_id,
                source_system=row.source_system,
                artifact_type=ArtifactType(row.artifact_type),
                source_artifact_id=row.source_artifact_id,
                title=row.title,
                content=row.content,
                structured_content=row.structured_content,
                author=row.author,
                created_at=row.created_at,
                updated_at=row.updated_at,
                source_url=row.source_url,
                checksum=row.checksum,
                embedding=row.embedding,
                ingestion_version=1,
            )
            await self._session.execute(
                statement.on_conflict_do_update(
                    constraint="uq_artifact_identity",
                    set_={
                        "title": statement.excluded.title,
                        "content": statement.excluded.content,
                        "structured_content": statement.excluded.structured_content,
                        "author": statement.excluded.author,
                        "created_at": statement.excluded.created_at,
                        "updated_at": statement.excluded.updated_at,
                        "source_url": statement.excluded.source_url,
                        "checksum": statement.excluded.checksum,
                        "embedding": statement.excluded.embedding,
                        "ingestion_version": Artifact.ingestion_version + 1,
                        "ingested_at": func.now(),
                    },
                )
            )

    async def update_metadata(self, workspace_id: uuid.UUID, rows: list[Artifact]) -> None:
        """Updates descriptive fields of pieces whose content is unchanged, leaving the
        stored embedding and version alone. Does not commit."""
        for row in rows:
            await self._session.execute(
                update(Artifact)
                .where(
                    Artifact.workspace_id == workspace_id,
                    Artifact.source_system == row.source_system,
                    Artifact.artifact_type == ArtifactType(row.artifact_type),
                    Artifact.source_artifact_id == row.source_artifact_id,
                )
                .values(
                    title=row.title,
                    source_url=row.source_url,
                    structured_content=row.structured_content,
                    author=row.author,
                    created_at=row.created_at,
                    updated_at=row.updated_at,
                )
            )

    async def delete_stale_source_file_pieces(
        self,
        workspace_id: uuid.UUID,
        source_system: SourceSystem,
        file_ids: list[str],
        current_piece_ids: set[str],
    ) -> None:
        """Removes pieces of the given files that the latest ingest no longer produced (a
        file that shrank, or flipped between one piece and several). Does not commit."""
        if not file_ids:
            return
        belongs_to_a_seen_file = or_(
            *(
                or_(
                    Artifact.source_artifact_id == file_id,
                    Artifact.source_artifact_id.startswith(f"{file_id}#chunk", autoescape=True),
                )
                for file_id in file_ids
            )
        )
        await self._session.execute(
            delete(Artifact).where(
                Artifact.workspace_id == workspace_id,
                Artifact.source_system == source_system,
                Artifact.artifact_type == ArtifactType.source_file,
                belongs_to_a_seen_file,
                Artifact.source_artifact_id.notin_(current_piece_ids),
            )
        )

    async def get_by_id(self, workspace_id: uuid.UUID, artifact_id: uuid.UUID) -> Artifact | None:
        result = await self._session.execute(
            select(Artifact).where(
                Artifact.workspace_id == workspace_id, Artifact.id == artifact_id
            )
        )
        return result.scalar_one_or_none()

    async def get_by_source_url(self, workspace_id: uuid.UUID, source_url: str) -> Artifact | None:
        result = await self._session.execute(
            select(Artifact).where(
                Artifact.workspace_id == workspace_id, Artifact.source_url == source_url
            )
        )
        return result.scalars().first()

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
