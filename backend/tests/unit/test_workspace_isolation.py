import pytest

from src.models.artifact import EMBEDDING_DIM, Artifact, ArtifactType, SourceSystem
from src.models.job import JobType
from src.models.relationship import RelationshipOrigin
from src.models.workspace import Workspace
from src.repositories.artifact_repository import ArtifactRepository
from src.repositories.connector_repository import ConnectorRepository
from src.repositories.job_repository import JobRepository
from src.repositories.relationship_repository import RelationshipRepository


async def _make_workspace(db_session, owner: str) -> Workspace:
    workspace = Workspace(owner_user_id=owner, name=owner)
    db_session.add(workspace)
    await db_session.commit()
    await db_session.refresh(workspace)
    return workspace


async def _two_workspaces(db_session) -> tuple[Workspace, Workspace]:
    return (
        await _make_workspace(db_session, "owner-a"),
        await _make_workspace(db_session, "owner-b"),
    )


@pytest.mark.asyncio
async def test_connector_repository_isolates_by_workspace(db_session):
    ws_a, ws_b = await _two_workspaces(db_session)
    repo = ConnectorRepository(db_session)
    connector_a = await repo.create(
        workspace_id=ws_a.id,
        source_system=SourceSystem.github,
        raw_access_token="token-a",
        external_resource_ref="acme/widgets",
    )

    assert await repo.get_by_id(ws_b.id, connector_a.id) is None
    assert await repo.list_by_workspace(ws_b.id) == []
    assert await repo.get_by_workspace_and_source(ws_b.id, SourceSystem.github) is None
    # Sanity check the same lookups succeed under the owning workspace.
    assert await repo.get_by_id(ws_a.id, connector_a.id) is not None
    assert len(await repo.list_by_workspace(ws_a.id)) == 1


@pytest.mark.asyncio
async def test_artifact_repository_isolates_by_workspace(db_session):
    ws_a, ws_b = await _two_workspaces(db_session)
    shared_url = "https://github.com/acme/widgets/blob/main/app.py"
    artifact_a = Artifact(
        workspace_id=ws_a.id,
        source_system=SourceSystem.github,
        source_artifact_id="1",
        artifact_type=ArtifactType.source_file,
        title="app.py",
        content="def foo(): pass",
        source_url=shared_url,
        embedding=[0.1] * EMBEDDING_DIM,
    )
    db_session.add(artifact_a)
    await db_session.commit()
    await db_session.refresh(artifact_a)

    repo = ArtifactRepository(db_session)

    assert await repo.get_by_id(ws_b.id, artifact_a.id) is None
    # Same source_url exists under ws_a — must not leak across workspaces.
    assert await repo.get_by_source_url(ws_b.id, shared_url) is None
    assert await repo.list_by_workspace(ws_b.id) == []
    assert await repo.search_fulltext(ws_b.id, "foo") == []
    assert await repo.search_by_embedding(ws_b.id, [0.1] * EMBEDDING_DIM) == []

    # Sanity check the same lookups succeed under the owning workspace.
    assert await repo.get_by_id(ws_a.id, artifact_a.id) is not None
    assert await repo.get_by_source_url(ws_a.id, shared_url) is not None
    assert len(await repo.list_by_workspace(ws_a.id)) == 1
    assert len(await repo.search_fulltext(ws_a.id, "foo")) == 1
    assert len(await repo.search_by_embedding(ws_a.id, [0.1] * EMBEDDING_DIM)) == 1


@pytest.mark.asyncio
async def test_relationship_repository_isolates_by_workspace(db_session):
    ws_a, ws_b = await _two_workspaces(db_session)
    doc = Artifact(
        workspace_id=ws_a.id,
        source_system=SourceSystem.notion,
        source_artifact_id="page-1",
        artifact_type=ArtifactType.document,
        title="Spec",
        content="See the PR.",
        source_url="https://notion.so/page-1",
    )
    pr = Artifact(
        workspace_id=ws_a.id,
        source_system=SourceSystem.github,
        source_artifact_id="1",
        artifact_type=ArtifactType.pull_request,
        title="Add spinner",
        content="Implements the spinner.",
        source_url="https://github.com/acme/widgets/pull/1",
    )
    db_session.add_all([doc, pr])
    await db_session.commit()
    await db_session.refresh(doc)
    await db_session.refresh(pr)

    rel_repo = RelationshipRepository(db_session)
    await rel_repo.create(
        workspace_id=ws_a.id,
        source_artifact_id=doc.id,
        target_artifact_id=pr.id,
        relationship_type="references",
        relationship_origin=RelationshipOrigin.explicit,
        evidence="https://github.com/acme/widgets/pull/1",
    )

    # Querying under ws_b for an artifact id that only exists in ws_a must
    # return nothing, even though the relationship row itself is real.
    assert await rel_repo.get_for_artifact(ws_b.id, doc.id) == []
    assert len(await rel_repo.get_for_artifact(ws_a.id, doc.id)) == 1


@pytest.mark.asyncio
async def test_job_repository_isolates_by_workspace(db_session):
    ws_a, ws_b = await _two_workspaces(db_session)
    connector = await ConnectorRepository(db_session).create(
        workspace_id=ws_a.id,
        source_system=SourceSystem.github,
        raw_access_token="token-a",
        external_resource_ref="acme/widgets",
    )
    job_repo = JobRepository(db_session)
    job = await job_repo.enqueue(ws_a.id, connector.id, JobType.ingest_github)

    assert await job_repo.get_by_id(ws_b.id, job.id) is None
    assert await job_repo.get_by_id(ws_a.id, job.id) is not None
