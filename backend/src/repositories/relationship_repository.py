import uuid

from sqlalchemy import or_, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.relationship import PHASE_1_ALLOWED_ORIGINS, Relationship, RelationshipOrigin


class RelationshipRepository:
    def __init__(self, session: AsyncSession):
        self._session = session

    async def create(
        self,
        workspace_id: uuid.UUID,
        source_artifact_id: uuid.UUID,
        target_artifact_id: uuid.UUID,
        relationship_type: str,
        relationship_origin: RelationshipOrigin,
        evidence: str | None = None,
        confidence: float | None = None,
    ) -> Relationship:
        relationship, _ = await self.create_if_absent(
            workspace_id,
            source_artifact_id,
            target_artifact_id,
            relationship_type,
            relationship_origin,
            evidence,
            confidence,
        )
        return relationship

    async def create_if_absent(
        self,
        workspace_id: uuid.UUID,
        source_artifact_id: uuid.UUID,
        target_artifact_id: uuid.UUID,
        relationship_type: str,
        relationship_origin: RelationshipOrigin,
        evidence: str | None = None,
        confidence: float | None = None,
    ) -> tuple[Relationship, bool]:
        """Returns the edge and whether this call created it. An existing edge is left
        exactly as it was."""
        if relationship_origin not in PHASE_1_ALLOWED_ORIGINS:
            # Constitution Principle II — Phase 1 code paths never write
            # model-inferred/user-confirmed relationships. The DB check
            # constraint would also reject a truly invalid value, but this
            # guards the narrower Phase 1 policy specifically.
            raise ValueError(
                f"Phase 1 may only write {PHASE_1_ALLOWED_ORIGINS}, got {relationship_origin}"
            )
        insert = (
            pg_insert(Relationship)
            .values(
                id=uuid.uuid4(),
                workspace_id=workspace_id,
                source_artifact_id=source_artifact_id,
                target_artifact_id=target_artifact_id,
                relationship_type=relationship_type,
                relationship_origin=relationship_origin,
                evidence=evidence,
                confidence=confidence,
            )
            .on_conflict_do_nothing(constraint="uq_relationship_edge")
            .returning(Relationship.id)
        )
        created = (await self._session.execute(insert)).scalar_one_or_none() is not None
        await self._session.commit()
        result = await self._session.execute(
            select(Relationship)
            .where(
                Relationship.workspace_id == workspace_id,
                Relationship.source_artifact_id == source_artifact_id,
                Relationship.target_artifact_id == target_artifact_id,
                Relationship.relationship_type == relationship_type,
            )
            .execution_options(populate_existing=True)
        )
        return result.scalar_one(), created

    async def get_for_artifact(
        self, workspace_id: uuid.UUID, artifact_id: uuid.UUID
    ) -> list[Relationship]:
        result = await self._session.execute(
            select(Relationship).where(
                Relationship.workspace_id == workspace_id,
                or_(
                    Relationship.source_artifact_id == artifact_id,
                    Relationship.target_artifact_id == artifact_id,
                ),
            )
        )
        return list(result.scalars().all())
