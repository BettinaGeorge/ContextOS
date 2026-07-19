import pytest

from src.models.artifact import EMBEDDING_DIM, Artifact, ArtifactType, SourceSystem
from src.models.workspace import Workspace
from src.services.retrieval_svc import RetrievalService


class FakeVoyageClient:
    def embed_query(self, text: str) -> list[float]:
        return [0.1] * EMBEDDING_DIM


@pytest.mark.asyncio
async def test_retrieve_merges_fulltext_and_vector_hits_without_duplicates(db_session):
    workspace = Workspace(owner_user_id="test-user", name="Test")
    db_session.add(workspace)
    await db_session.commit()
    await db_session.refresh(workspace)

    exact_match = Artifact(
        workspace_id=workspace.id,
        source_system=SourceSystem.github,
        source_artifact_id="1",
        artifact_type=ArtifactType.source_file,
        title="spinner.py",
        content="def spin_widget(): pass",
        source_url="https://github.com/acme/widgets/blob/HEAD/spinner.py",
        embedding=[0.1] * EMBEDDING_DIM,
    )
    unrelated = Artifact(
        workspace_id=workspace.id,
        source_system=SourceSystem.github,
        source_artifact_id="2",
        artifact_type=ArtifactType.source_file,
        title="unrelated.py",
        content="def totally_different_thing(): pass",
        source_url="https://github.com/acme/widgets/blob/HEAD/unrelated.py",
        embedding=[0.9] * EMBEDDING_DIM,
    )
    db_session.add_all([exact_match, unrelated])
    await db_session.commit()

    results = await RetrievalService(db_session, voyage_client=FakeVoyageClient()).retrieve(
        workspace.id, "spin_widget"
    )

    ids = [r.id for r in results]
    assert exact_match.id in ids
    # exact_match should not appear twice even though it can match both
    # full-text and vector search.
    assert ids.count(exact_match.id) == 1
