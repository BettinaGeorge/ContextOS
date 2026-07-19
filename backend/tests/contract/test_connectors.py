import pytest


async def _create_workspace(client, token):
    resp = await client.post(
        "/workspaces", json={"name": "Test"}, headers={"Authorization": f"Bearer {token}"}
    )
    assert resp.status_code == 201
    return resp.json()["id"]


@pytest.mark.asyncio
async def test_connect_github_requires_workspace_first(client, make_jwt):
    token = make_jwt()
    resp = await client.post(
        "/connectors/github",
        json={"repo": "acme/widgets", "auth_code_or_token": "fake"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_connect_github_succeeds_and_conflicts_on_second_attempt(client, make_jwt):
    token = make_jwt()
    headers = {"Authorization": f"Bearer {token}"}
    await _create_workspace(client, token)

    first = await client.post(
        "/connectors/github",
        json={"repo": "acme/widgets", "auth_code_or_token": "fake"},
        headers=headers,
    )
    assert first.status_code == 202
    body = first.json()
    assert body["status"] == "connected"
    assert "connector_id" in body

    second = await client.post(
        "/connectors/github",
        json={"repo": "acme/other-repo", "auth_code_or_token": "fake"},
        headers=headers,
    )
    assert second.status_code == 409


@pytest.mark.asyncio
async def test_connect_notion_succeeds(client, make_jwt):
    token = make_jwt()
    headers = {"Authorization": f"Bearer {token}"}
    await _create_workspace(client, token)

    resp = await client.post(
        "/connectors/notion",
        json={"integration_token": "fake", "page_ids": ["page-1", "page-2"]},
        headers=headers,
    )
    assert resp.status_code == 202
    assert resp.json()["status"] == "connected"


@pytest.mark.asyncio
async def test_connector_status_returns_404_for_unknown_connector(client, make_jwt):
    token = make_jwt()
    headers = {"Authorization": f"Bearer {token}"}
    await _create_workspace(client, token)

    resp = await client.get(
        "/connectors/00000000-0000-0000-0000-000000000000/status", headers=headers
    )
    assert resp.status_code == 404
