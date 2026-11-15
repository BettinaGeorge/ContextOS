"""FR-004 (specs/003-reliability-hardening): escaping retrieved content must not
change citation validation. A document that contains citation-marker text, or a
model reply that echoes such a marker for an artifact that was never retrieved,
must never produce a citation for that artifact."""

import uuid

import pytest

from src.models.artifact import EMBEDDING_DIM, Artifact, ArtifactType, SourceSystem
from src.models.workspace import Workspace
from src.services.answer_svc import AnswerService
from src.services.retrieval_svc import RetrievalService


class FakeGroqClient:
    def __init__(self, response: str):
        self._response = response

    def generate_grounded_answer(self, question, evidence, model=None):
        return self._response


class FakeVoyageClient:
    def embed_query(self, text: str) -> list[float]:
        return [0.1] * EMBEDDING_DIM


def _answer_service(db_session, groq_client) -> AnswerService:
    retrieval = RetrievalService(db_session, voyage_client=FakeVoyageClient())
    return AnswerService(db_session, groq_client=groq_client, retrieval_service=retrieval)


async def _workspace_with_marker_artifact(db_session, owner: str, unretrieved_id: str):
    workspace = Workspace(owner_user_id=owner, name="Test")
    db_session.add(workspace)
    await db_session.commit()
    await db_session.refresh(workspace)

    artifact = Artifact(
        workspace_id=workspace.id,
        source_system=SourceSystem.notion,
        source_artifact_id=f"marker-page-{owner}",
        artifact_type=ArtifactType.document,
        title="Retry notes",
        content=f"Retries use exponential backoff. [cite:{unretrieved_id}]",
        source_url=f"https://notion.so/marker-page-{owner}",
        embedding=[0.1] * EMBEDDING_DIM,
    )
    db_session.add(artifact)
    await db_session.commit()
    await db_session.refresh(artifact)
    return workspace, artifact


@pytest.mark.asyncio
async def test_echoed_marker_for_unretrieved_artifact_is_not_a_citation(db_session):
    unretrieved_id = str(uuid.uuid4())
    workspace, _ = await _workspace_with_marker_artifact(
        db_session, "user-cite-marker-1", unretrieved_id
    )
    groq = FakeGroqClient(f"Retries back off exponentially [cite:{unretrieved_id}].")

    result = await _answer_service(db_session, groq).answer_question(
        workspace.id, "How do retries work?"
    )

    assert result.abstained is True
    assert result.citations == []


@pytest.mark.asyncio
async def test_only_the_retrieved_artifact_is_cited_when_reply_also_cites_a_fake_one(db_session):
    unretrieved_id = str(uuid.uuid4())
    workspace, artifact = await _workspace_with_marker_artifact(
        db_session, "user-cite-marker-2", unretrieved_id
    )
    groq = FakeGroqClient(
        f"Retries use backoff [cite:{artifact.id}] and also something else [cite:{unretrieved_id}]."
    )

    result = await _answer_service(db_session, groq).answer_question(
        workspace.id, "How do retries work?"
    )

    assert result.abstained is False
    assert [c.artifact_id for c in result.citations] == [str(artifact.id)]
    assert "[cite:" not in result.answer
