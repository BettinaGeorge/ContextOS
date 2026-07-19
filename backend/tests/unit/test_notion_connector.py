import httpx
import pytest
import respx

from src.connectors.base import ConnectorAuthError
from src.connectors.notion_connector import NotionConnector, extract_github_links


@pytest.fixture
def connector():
    return NotionConnector(integration_token="fake-token", page_ids=["page-1"])


@pytest.mark.asyncio
@respx.mock
async def test_authenticate_succeeds(connector):
    respx.get("https://api.notion.com/v1/users/me").mock(
        return_value=httpx.Response(200, json={"id": "user-1", "type": "bot"})
    )
    await connector.authenticate()  # should not raise


@pytest.mark.asyncio
@respx.mock
async def test_authenticate_raises_connector_auth_error_on_unauthorized(connector):
    respx.get("https://api.notion.com/v1/users/me").mock(
        return_value=httpx.Response(
            401,
            json={
                "object": "error",
                "status": 401,
                "code": "unauthorized",
                "message": "API token is invalid.",
            },
        )
    )
    with pytest.raises(ConnectorAuthError):
        await connector.authenticate()


@pytest.mark.asyncio
@respx.mock
async def test_ingest_full_normalizes_page_with_blocks(connector):
    respx.get("https://api.notion.com/v1/pages/page-1").mock(
        return_value=httpx.Response(
            200,
            json={
                "id": "page-1",
                "url": "https://notion.so/page-1",
                "created_time": "2026-01-01T00:00:00.000Z",
                "last_edited_time": "2026-01-02T00:00:00.000Z",
                "properties": {
                    "title": {
                        "type": "title",
                        "title": [{"plain_text": "Widget Spinner Spec"}],
                    }
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
                        "id": "block-1",
                        "type": "paragraph",
                        "has_children": False,
                        "paragraph": {
                            "rich_text": [
                                {
                                    "plain_text": (
                                        "See https://github.com/acme/widgets/pull/1 for impl."
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

    artifacts = await connector.ingest_full()
    assert len(artifacts) == 1
    doc = artifacts[0]
    assert doc.artifact_type == "document"
    assert doc.title == "Widget Spinner Spec"
    assert "github.com/acme/widgets/pull/1" in doc.content
    assert doc.source_url == "https://notion.so/page-1"


def test_extract_github_links_finds_pr_and_commit_urls():
    text = (
        "Implemented in https://github.com/acme/widgets/pull/42 "
        "and https://github.com/acme/widgets/commit/deadbeef1234, see also unrelated text."
    )
    links = extract_github_links(text)
    assert "https://github.com/acme/widgets/pull/42" in links
    assert "https://github.com/acme/widgets/commit/deadbeef1234" in links


def test_extract_github_links_returns_empty_for_no_links():
    assert extract_github_links("Just a plain spec doc with no links.") == []
