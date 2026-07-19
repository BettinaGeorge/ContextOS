import pytest

from src.models.artifact import EMBEDDING_DIM, Artifact, ArtifactType, SourceSystem
from src.models.relationship import RelationshipOrigin
from src.models.workspace import Workspace
from src.repositories.relationship_repository import RelationshipRepository
from src.services.answer_svc import AnswerService
from src.services.retrieval_svc import RetrievalService


class FakeClaudeClient:
    def __init__(self, response: str):
        self._response = response

    def generate_grounded_answer(self, question, evidence, model=None):
        return self._response


class FakeVoyageClient:
    def embed_query(self, text: str) -> list[float]:
        return [0.1] * EMBEDDING_DIM


def _answer_service(db_session, claude_client) -> AnswerService:
    retrieval = RetrievalService(db_session, voyage_client=FakeVoyageClient())
    return AnswerService(db_session, claude_client=claude_client, retrieval_service=retrieval)


async def _make_workspace(db_session, owner):
    workspace = Workspace(owner_user_id=owner, name="Test")
    db_session.add(workspace)
    await db_session.commit()
    await db_session.refresh(workspace)
    return workspace


@pytest.mark.asyncio
async def test_abstains_with_zero_evidence_without_calling_llm(db_session):
    workspace = await _make_workspace(db_session, "user-empty")

    class ExplodingClaudeClient:
        def generate_grounded_answer(self, *a, **kw):
            raise AssertionError("must not call the LLM when there is no evidence at all")

    result = await _answer_service(db_session, ExplodingClaudeClient()).answer_question(
        workspace.id, "What does this do?"
    )
    assert result.abstained is True
    assert result.citations == []


@pytest.mark.asyncio
async def test_deterministic_citation_labeled_explicit(db_session):
    workspace = await _make_workspace(db_session, "user-explicit")
    pr = Artifact(
        workspace_id=workspace.id,
        source_system=SourceSystem.github,
        source_artifact_id="1",
        artifact_type=ArtifactType.pull_request,
        title="Add spinner",
        content="Implements the spinner widget.",
        source_url="https://github.com/acme/widgets/pull/1",
    )
    doc = Artifact(
        workspace_id=workspace.id,
        source_system=SourceSystem.notion,
        source_artifact_id="page-1",
        artifact_type=ArtifactType.document,
        title="Spinner Spec",
        content="See the PR for implementation.",
        source_url="https://notion.so/page-1",
    )
    db_session.add_all([pr, doc])
    await db_session.commit()
    await db_session.refresh(pr)
    await db_session.refresh(doc)

    await RelationshipRepository(db_session).create(
        workspace_id=workspace.id,
        source_artifact_id=doc.id,
        target_artifact_id=pr.id,
        relationship_type="references",
        relationship_origin=RelationshipOrigin.explicit,
        evidence="https://github.com/acme/widgets/pull/1",
    )

    fake_response = f"The spinner is implemented in the linked PR. [cite:{pr.id}]"
    result = await _answer_service(db_session, FakeClaudeClient(fake_response)).answer_question(
        workspace.id, "What implements the spinner?", notion_doc_url="https://notion.so/page-1"
    )

    assert result.abstained is False
    assert len(result.citations) == 1
    assert result.citations[0].artifact_id == str(pr.id)
    assert result.citations[0].origin == "explicit"
    assert "[cite:" not in result.answer


@pytest.mark.asyncio
async def test_insufficient_evidence_marker_triggers_abstention(db_session):
    workspace = await _make_workspace(db_session, "user-insufficient")
    doc = Artifact(
        workspace_id=workspace.id,
        source_system=SourceSystem.notion,
        source_artifact_id="page-2",
        artifact_type=ArtifactType.document,
        title="Unrelated Spec",
        content="Nothing about the topic asked.",
        source_url="https://notion.so/page-2",
    )
    db_session.add(doc)
    await db_session.commit()

    fake_response = "[INSUFFICIENT_EVIDENCE] Nothing in the evidence addresses this question."
    result = await _answer_service(db_session, FakeClaudeClient(fake_response)).answer_question(
        workspace.id,
        "What implements the flux capacitor?",
        notion_doc_url="https://notion.so/page-2",
    )
    assert result.abstained is True
    assert result.citations == []
    assert "INSUFFICIENT_EVIDENCE" not in result.answer


@pytest.mark.asyncio
async def test_hallucinated_citation_id_is_dropped_and_forces_abstention(db_session):
    workspace = await _make_workspace(db_session, "user-halluc")
    doc = Artifact(
        workspace_id=workspace.id,
        source_system=SourceSystem.notion,
        source_artifact_id="page-3",
        artifact_type=ArtifactType.document,
        title="Some Spec",
        content="Some content.",
        source_url="https://notion.so/page-3",
    )
    db_session.add(doc)
    await db_session.commit()

    # Model cites an artifact_id that was never in the evidence packet.
    fake_response = "This is implemented somewhere. [cite:00000000-0000-0000-0000-000000000000]"
    result = await _answer_service(db_session, FakeClaudeClient(fake_response)).answer_question(
        workspace.id, "some question", notion_doc_url="https://notion.so/page-3"
    )
    # FR-013: the fabricated id must never surface as a real citation, and a
    # confident-sounding answer with zero valid citations must abstain.
    assert result.abstained is True
    assert result.citations == []
