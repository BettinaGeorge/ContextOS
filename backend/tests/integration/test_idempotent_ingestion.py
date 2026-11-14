"""SC-001 (specs/003): ingesting the same source twice changes nothing and costs nothing."""

import pytest
from _ingestion_support import (
    TWO_FUNCTIONS,
    CountingVoyage,
    make_workspace,
    notion_page,
    pull_request,
    source_file,
    stored_artifacts,
)
from sqlalchemy import func, select

from src.models.artifact import SourceSystem
from src.models.relationship import Relationship
from src.services.connector_svc import ConnectorService
from src.services.relationship_svc import RelationshipService


async def _run_full_ingestion(db_session, workspace, voyage) -> None:
    service = ConnectorService(db_session, voyage_client=voyage)
    await service.ingest_normalized(
        workspace.id,
        SourceSystem.github,
        [source_file("app.py", TWO_FUNCTIONS), pull_request(1)],
    )
    await service.ingest_normalized(
        workspace.id,
        SourceSystem.notion,
        [notion_page("page-1", "See https://github.com/acme/widgets/pull/1 for the code.")],
    )
    await RelationshipService(db_session).extract_for_workspace(workspace.id)


async def _relationship_count(db_session, workspace_id) -> int:
    result = await db_session.execute(
        select(func.count())
        .select_from(Relationship)
        .where(Relationship.workspace_id == workspace_id)
    )
    return result.scalar_one()


@pytest.mark.asyncio
async def test_second_ingestion_adds_nothing_and_embeds_nothing(db_session):
    workspace = await make_workspace(db_session)
    voyage = CountingVoyage()

    await _run_full_ingestion(db_session, workspace, voyage)
    artifacts_after_first = await stored_artifacts(db_session, workspace.id)
    relationships_after_first = await _relationship_count(db_session, workspace.id)
    embedded_after_first = len(voyage.embedded_texts)
    assert embedded_after_first > 0 and relationships_after_first == 1

    await _run_full_ingestion(db_session, workspace, voyage)

    artifacts_after_second = await stored_artifacts(db_session, workspace.id)
    assert len(artifacts_after_second) == len(artifacts_after_first)
    assert {a.id for a in artifacts_after_second} == {a.id for a in artifacts_after_first}
    assert await _relationship_count(db_session, workspace.id) == relationships_after_first
    assert len(voyage.embedded_texts) == embedded_after_first
    assert all(a.ingestion_version == 1 for a in artifacts_after_second)


@pytest.mark.asyncio
async def test_many_repeated_ingestions_stay_stable(db_session):
    workspace = await make_workspace(db_session)
    voyage = CountingVoyage()

    for _ in range(4):
        await _run_full_ingestion(db_session, workspace, voyage)

    assert len(await stored_artifacts(db_session, workspace.id)) == 4
    assert await _relationship_count(db_session, workspace.id) == 1
