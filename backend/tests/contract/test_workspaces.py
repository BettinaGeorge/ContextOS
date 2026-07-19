import pytest


@pytest.mark.asyncio
async def test_create_workspace_requires_auth(client):
    response = await client.post("/workspaces", json={"name": "My Workspace"})
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_create_workspace_returns_workspace(client, make_jwt):
    token = make_jwt()
    response = await client.post(
        "/workspaces",
        json={"name": "My Workspace"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 201
    body = response.json()
    assert body["name"] == "My Workspace"
    assert "id" in body
    assert "created_at" in body


@pytest.mark.asyncio
async def test_create_second_workspace_conflicts(client, make_jwt):
    token = make_jwt()
    headers = {"Authorization": f"Bearer {token}"}
    first = await client.post("/workspaces", json={"name": "First"}, headers=headers)
    assert first.status_code == 201

    second = await client.post("/workspaces", json={"name": "Second"}, headers=headers)
    assert second.status_code == 409
    assert second.json()["error"]
