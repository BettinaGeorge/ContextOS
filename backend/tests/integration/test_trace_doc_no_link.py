"""Integration test for quickstart.md scenario 3 / spec.md US1 Acceptance
Scenario 3: a Notion doc with no explicit GitHub link. The response must
either cite semantically-related code labeled "inferred", or explicitly
abstain — never present an inferred match with the same certainty as a
deterministic one. Added per the /speckit-analyze E1 finding (originally
uncovered by any test)."""

import pytest

from src.models.artifact import EMBEDDING_DIM, Artifact, ArtifactType, SourceSystem
from src.models.workspace import Workspace
from src.services.answer_svc import AnswerService
from src.services.retrieval_svc import RetrievalService


class FakeVoyageClient:
    def embed_query(self, text):
        return [0.1] * EMBEDDING_DIM


class FakeGroqClientCitesInferred:
    """A model that finds the semantically-related file and cites it,
    correctly relying on the evidence's origin="inferred" label rather than
    claiming certainty."""

    def generate_grounded_answer(self, question, evidence, model=None):
        code_items = [e for e in evidence if e.artifact_type == "source_file"]
        # No relationship row connects the anchor doc to this file — it can
        # only have been found via retrieval, so it must be labeled inferred.
        # (The anchor doc itself is separately labeled "explicit" because the
        # user directly identified it via notion_doc_url — a different,
        # legitimate reason, not a relationship between two artifacts.)
        assert all(e.origin == "inferred" for e in code_items)
        if not code_items:
            return "[INSUFFICIENT_EVIDENCE] No related code found."
        return f"Possibly related: the spinner logic. [cite:{code_items[0].artifact_id}]"


class FakeGroqClientAbstains:
    def generate_grounded_answer(self, question, evidence, model=None):
        return "[INSUFFICIENT_EVIDENCE] No confident match found in the evidence."


async def _make_workspace_with_doc_and_file(db_session, owner):
    workspace = Workspace(owner_user_id=owner, name="Test")
    db_session.add(workspace)
    await db_session.commit()
    await db_session.refresh(workspace)

    doc = Artifact(
        workspace_id=workspace.id,
        source_system=SourceSystem.notion,
        source_artifact_id="page-x",
        artifact_type=ArtifactType.document,
        title="Spinner Spec",
        content="The spinner should rotate smoothly. No links to any PR here.",
        source_url="https://notion.so/page-x",
        embedding=[0.1] * EMBEDDING_DIM,
    )
    code = Artifact(
        workspace_id=workspace.id,
        source_system=SourceSystem.github,
        source_artifact_id="sha1",
        artifact_type=ArtifactType.source_file,
        title="spinner.py",
        content="def spin(): ...",
        source_url="https://github.com/acme/widgets/blob/HEAD/spinner.py",
        embedding=[0.1] * EMBEDDING_DIM,
    )
    db_session.add_all([doc, code])
    await db_session.commit()
    return workspace, doc, code


@pytest.mark.asyncio
async def test_no_deterministic_link_returns_inferred_citation_not_explicit(db_session):
    workspace, doc, _code = await _make_workspace_with_doc_and_file(db_session, "user-inferred")

    retrieval = RetrievalService(db_session, voyage_client=FakeVoyageClient())
    answer_svc = AnswerService(
        db_session, groq_client=FakeGroqClientCitesInferred(), retrieval_service=retrieval
    )
    result = await answer_svc.answer_question(
        workspace.id, "What implements the spinner?", notion_doc_url=doc.source_url
    )

    assert result.abstained is False
    assert len(result.citations) == 1
    # Never presented as deterministic — no relationship row links these two.
    assert result.citations[0].origin == "inferred"


@pytest.mark.asyncio
async def test_no_deterministic_link_and_model_uncertain_abstains(db_session):
    workspace, doc, _code = await _make_workspace_with_doc_and_file(db_session, "user-abstain")

    retrieval = RetrievalService(db_session, voyage_client=FakeVoyageClient())
    answer_svc = AnswerService(
        db_session, groq_client=FakeGroqClientAbstains(), retrieval_service=retrieval
    )
    result = await answer_svc.answer_question(
        workspace.id, "What implements the spinner?", notion_doc_url=doc.source_url
    )

    assert result.abstained is True
    assert result.citations == []
