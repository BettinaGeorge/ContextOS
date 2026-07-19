import pytest

from src.models.artifact import Artifact, ArtifactType, SourceSystem
from src.models.workspace import Workspace
from src.repositories.relationship_repository import RelationshipRepository
from src.services.relationship_svc import RelationshipService


@pytest.mark.asyncio
async def test_extracts_explicit_link_from_notion_doc_to_github_pr(db_session):
    workspace = Workspace(owner_user_id="test-user", name="Test")
    db_session.add(workspace)
    await db_session.commit()
    await db_session.refresh(workspace)

    pr = Artifact(
        workspace_id=workspace.id,
        source_system=SourceSystem.github,
        source_artifact_id="1",
        artifact_type=ArtifactType.pull_request,
        title="Add spinner",
        content="Implements the spinner.",
        source_url="https://github.com/acme/widgets/pull/1",
    )
    doc = Artifact(
        workspace_id=workspace.id,
        source_system=SourceSystem.notion,
        source_artifact_id="page-1",
        artifact_type=ArtifactType.document,
        title="Spinner Spec",
        content="See https://github.com/acme/widgets/pull/1 for the implementation.",
        source_url="https://notion.so/page-1",
    )
    db_session.add_all([pr, doc])
    await db_session.commit()

    created = await RelationshipService(db_session).extract_for_workspace(workspace.id)
    assert created == 1

    relationships = await RelationshipRepository(db_session).get_for_artifact(workspace.id, doc.id)
    assert len(relationships) == 1
    assert relationships[0].target_artifact_id == pr.id
    assert relationships[0].relationship_origin == "explicit"


@pytest.mark.asyncio
async def test_no_relationship_created_when_no_link_present(db_session):
    workspace = Workspace(owner_user_id="test-user-2", name="Test 2")
    db_session.add(workspace)
    await db_session.commit()
    await db_session.refresh(workspace)

    doc = Artifact(
        workspace_id=workspace.id,
        source_system=SourceSystem.notion,
        source_artifact_id="page-2",
        artifact_type=ArtifactType.document,
        title="Unrelated Doc",
        content="No links here at all.",
        source_url="https://notion.so/page-2",
    )
    db_session.add(doc)
    await db_session.commit()

    created = await RelationshipService(db_session).extract_for_workspace(workspace.id)
    assert created == 0
