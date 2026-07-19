"""Integration test for quickstart.md scenarios 1-2: connect GitHub + Notion,
ingest both, ask a question about a doc with an explicit deterministic link
to a PR, and confirm a correctly-cited answer comes back."""

import httpx
import pytest
import respx

from src.models.artifact import EMBEDDING_DIM
from src.models.connector import SourceSystem
from src.models.workspace import Workspace
from src.repositories.connector_repository import ConnectorRepository
from src.services.answer_svc import AnswerService
from src.services.connector_svc import ConnectorService
from src.services.relationship_svc import RelationshipService
from src.services.retrieval_svc import RetrievalService


class FakeVoyageClient:
    def embed_documents(self, texts):
        return [[0.1] * EMBEDDING_DIM for _ in texts]

    def embed_query(self, text):
        return [0.1] * EMBEDDING_DIM


class FakeGroqClient:
    """Simulates a well-behaved model that cites whatever PR-typed evidence
    item it's given — good enough to prove the pipeline wires evidence
    through correctly without needing a live Groq call."""

    def generate_grounded_answer(self, question, evidence, model=None):
        pr_items = [e for e in evidence if e.artifact_type == "pull_request"]
        if not pr_items:
            return "[INSUFFICIENT_EVIDENCE] No pull request evidence available."
        pr_id = pr_items[0].artifact_id
        return f"The spinner is implemented in the linked pull request. [cite:{pr_id}]"


@pytest.mark.asyncio
@respx.mock
async def test_connect_ingest_and_ask_returns_deterministic_citation(db_session):
    workspace = Workspace(owner_user_id="integration-user", name="Integration Test")
    db_session.add(workspace)
    await db_session.commit()
    await db_session.refresh(workspace)

    # --- Scenario 1: connect GitHub + Notion, ingest both ---
    connectors = ConnectorRepository(db_session)
    github_connector = await connectors.create(
        workspace_id=workspace.id,
        source_system=SourceSystem.github,
        raw_access_token="fake-gh-token",
        external_resource_ref="acme/widgets",
    )
    notion_connector = await connectors.create(
        workspace_id=workspace.id,
        source_system=SourceSystem.notion,
        raw_access_token="fake-notion-token",
        external_resource_ref="page-1",
    )

    respx.get("https://api.github.com/repos/acme/widgets").mock(
        return_value=httpx.Response(200, json={"default_branch": "main"})
    )
    respx.get("https://api.github.com/repos/acme/widgets/git/trees/main").mock(
        return_value=httpx.Response(200, json={"tree": []})
    )
    respx.get("https://api.github.com/repos/acme/widgets/pulls").mock(
        return_value=httpx.Response(
            200,
            json=[
                {
                    "number": 1,
                    "title": "Add spinner",
                    "body": "Implements the spinner widget.",
                    "html_url": "https://github.com/acme/widgets/pull/1",
                    "user": {"login": "octocat"},
                    "created_at": "2026-01-01T00:00:00Z",
                    "updated_at": "2026-01-01T00:00:00Z",
                    "state": "closed",
                    "merged_at": "2026-01-01T00:00:00Z",
                }
            ],
        )
    )
    respx.get("https://api.github.com/repos/acme/widgets/commits").mock(
        return_value=httpx.Response(200, json=[])
    )
    respx.get("https://api.github.com/repos/acme/widgets/issues").mock(
        return_value=httpx.Response(200, json=[])
    )
    respx.get("https://api.notion.com/v1/users/me").mock(
        return_value=httpx.Response(200, json={"id": "bot", "type": "bot"})
    )
    respx.get("https://api.notion.com/v1/pages/page-1").mock(
        return_value=httpx.Response(
            200,
            json={
                "id": "page-1",
                "url": "https://notion.so/page-1",
                "created_time": "2026-01-01T00:00:00.000Z",
                "last_edited_time": "2026-01-01T00:00:00.000Z",
                "properties": {
                    "title": {"type": "title", "title": [{"plain_text": "Spinner Spec"}]}
                },
            },
        )
    )
    respx.get("https://api.notion.com/v1/blocks/page-1/children").mock(
        return_value=httpx.Response(
            200,
            json={
                "results": [
                    {
                        "id": "b1",
                        "type": "paragraph",
                        "has_children": False,
                        "paragraph": {
                            "rich_text": [
                                {
                                    "plain_text": (
                                        "See https://github.com/acme/widgets/pull/1 "
                                        "for the implementation."
                                    )
                                }
                            ]
                        },
                    }
                ],
                "has_more": False,
                "next_cursor": None,
            },
        )
    )

    connector_svc = ConnectorService(db_session, voyage_client=FakeVoyageClient())
    gh_count = await connector_svc.ingest(workspace.id, github_connector)
    notion_count = await connector_svc.ingest(workspace.id, notion_connector)
    assert gh_count == 1  # the one PR
    assert notion_count == 1  # the one page

    # Deterministic relationship extraction (research.md §4)
    relationships_created = await RelationshipService(db_session).extract_for_workspace(
        workspace.id
    )
    assert relationships_created == 1

    # --- Scenario 2: ask a question, get a deterministically-cited answer ---
    retrieval = RetrievalService(db_session, voyage_client=FakeVoyageClient())
    answer_svc = AnswerService(
        db_session, groq_client=FakeGroqClient(), retrieval_service=retrieval
    )
    result = await answer_svc.answer_question(
        workspace.id,
        "What implements the spinner?",
        notion_doc_url="https://notion.so/page-1",
    )

    assert result.abstained is False
    assert len(result.citations) == 1
    assert result.citations[0].origin == "explicit"
    assert result.citations[0].source_url == "https://github.com/acme/widgets/pull/1"
