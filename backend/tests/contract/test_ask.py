import pytest

from src.api.ask import get_answer_service
from src.main import app
from src.services.answer_svc import AnswerResult, Citation


class FakeAnswerService:
    def __init__(self, result: AnswerResult):
        self._result = result

    async def answer_question(self, workspace_id, question, notion_doc_url=None):
        return self._result


@pytest.fixture(autouse=True)
def clear_overrides():
    yield
    app.dependency_overrides.pop(get_answer_service, None)


async def _create_workspace(client, token):
    resp = await client.post(
        "/workspaces", json={"name": "Test"}, headers={"Authorization": f"Bearer {token}"}
    )
    assert resp.status_code == 201


@pytest.mark.asyncio
async def test_ask_returns_deterministic_citation(client, make_jwt):
    token = make_jwt()
    await _create_workspace(client, token)

    fake_result = AnswerResult(
        answer="The spinner is implemented in the linked PR.",
        abstained=False,
        citations=[
            Citation(
                artifact_id="11111111-1111-1111-1111-111111111111",
                source_url="https://github.com/acme/widgets/pull/1",
                artifact_type="pull_request",
                origin="explicit",
            )
        ],
    )
    app.dependency_overrides[get_answer_service] = lambda: FakeAnswerService(fake_result)

    resp = await client.post(
        "/ask",
        json={"question": "What implements the spinner?", "notion_doc_url": None},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["abstained"] is False
    assert len(body["citations"]) == 1
    assert body["citations"][0]["origin"] == "explicit"


@pytest.mark.asyncio
async def test_ask_requires_workspace(client, make_jwt):
    token = make_jwt()
    resp = await client.post(
        "/ask", json={"question": "anything"}, headers={"Authorization": f"Bearer {token}"}
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_ask_returns_abstained_response(client, make_jwt):
    token = make_jwt()
    await _create_workspace(client, token)

    fake_result = AnswerResult(answer="No relevant evidence was found.", abstained=True)
    app.dependency_overrides[get_answer_service] = lambda: FakeAnswerService(fake_result)

    resp = await client.post(
        "/ask", json={"question": "unrelated"}, headers={"Authorization": f"Bearer {token}"}
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["abstained"] is True
    assert body["citations"] == []
