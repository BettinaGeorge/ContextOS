"""FR-010 (specs/003): extracting relationships twice yields each edge once."""

import pytest
from sqlalchemy import select

from src.models.artifact import Artifact, ArtifactType, SourceSystem
from src.models.relationship import Relationship
from src.models.workspace import Workspace
from src.services.relationship_svc import RelationshipService


async def _workspace_with_linked_artifacts(db_session):
    workspace = Workspace(owner_user_id="rel-idempotent-test", name="Test")
    db_session.add(workspace)
    await db_session.commit()
    await db_session.refresh(workspace)

    pr = Artifact(
        workspace_id=workspace.id,
        source_system=SourceSystem.github,
        source_artifact_id="1",
        artifact_type=ArtifactType.pull_request,
        title="Add spinner",
        content="Spec lives at https://notion.so/page-2",
        source_url="https://github.com/acme/widgets/pull/1",
    )
    doc_forward = Artifact(
        workspace_id=workspace.id,
        source_system=SourceSystem.notion,
        source_artifact_id="page-1",
        artifact_type=ArtifactType.document,
        title="Spinner Spec",
        content="See https://github.com/acme/widgets/pull/1 for the implementation.",
        source_url="https://notion.so/page-1",
    )
    doc_reverse = Artifact(
        workspace_id=workspace.id,
        source_system=SourceSystem.notion,
        source_artifact_id="page-2",
        artifact_type=ArtifactType.document,
        title="Spinner Design",
        content="No links in this one.",
        source_url="https://notion.so/page-2",
    )
    db_session.add_all([pr, doc_forward, doc_reverse])
    await db_session.commit()
    return workspace


async def _edges(db_session, workspace_id) -> list[tuple]:
    result = await db_session.execute(
        select(
            Relationship.source_artifact_id,
            Relationship.target_artifact_id,
            Relationship.relationship_type,
        ).where(Relationship.workspace_id == workspace_id)
    )
    return [tuple(row) for row in result.all()]


@pytest.mark.asyncio
async def test_extracting_twice_creates_each_edge_once_and_reports_zero_the_second_time(
    db_session,
):
    workspace = await _workspace_with_linked_artifacts(db_session)
    service = RelationshipService(db_session)

    first = await service.extract_for_workspace(workspace.id)
    edges_after_first = await _edges(db_session, workspace.id)
    second = await service.extract_for_workspace(workspace.id)
    edges_after_second = await _edges(db_session, workspace.id)

    assert first == 2
    assert second == 0
    assert len(edges_after_first) == 2
    assert sorted(edges_after_second) == sorted(edges_after_first)
    assert len(set(edges_after_second)) == len(edges_after_second)
