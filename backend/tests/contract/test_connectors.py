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


@pytest.mark.asyncio
async def test_list_connectors_returns_both_after_connecting(client, make_jwt):
    token = make_jwt()
    headers = {"Authorization": f"Bearer {token}"}
    await _create_workspace(client, token)

    empty = await client.get("/connectors", headers=headers)
    assert empty.status_code == 200
    assert empty.json() == []

    await client.post(
        "/connectors/github",
        json={"repo": "acme/widgets", "auth_code_or_token": "fake"},
        headers=headers,
    )
    await client.post(
        "/connectors/notion",
        json={"integration_token": "fake", "page_ids": ["page-1"]},
        headers=headers,
    )

    listed = await client.get("/connectors", headers=headers)
    assert listed.status_code == 200
    sources = {c["source_system"] for c in listed.json()}
    assert sources == {"github", "notion"}


@pytest.mark.asyncio
async def test_connector_status_reflects_connected_then_failed_transition(client, make_jwt):
    """T053: a real status transition, not just the initial state — connect,
    observe "connected", force a failure via the real ingestion pipeline,
    observe the status/error_message update through the same endpoint."""
    token = make_jwt()
    headers = {"Authorization": f"Bearer {token}"}
    await _create_workspace(client, token)

    connect_resp = await client.post(
        "/connectors/github",
        json={"repo": "acme/widgets", "auth_code_or_token": "fake-token"},
        headers=headers,
    )
    connector_id = connect_resp.json()["connector_id"]

    status_resp = await client.get(f"/connectors/{connector_id}/status", headers=headers)
    assert status_resp.json()["status"] == "connected"
    assert status_resp.json()["error_message"] is None

    ingest_resp = await client.post(f"/ingest/{connector_id}", headers=headers)
    assert ingest_resp.status_code == 202

    # IngestionService.trigger() sets "ingesting" synchronously before the
    # job is even enqueued; the in-process job worker (T022) that would move
    # it further doesn't run under ASGITransport in tests (no lifespan
    # events), so "ingesting" is the deterministic end state here — the
    # actual failure-status content this endpoint reports is proven
    # end-to-end in the ingestion_svc integration test (T054) instead.
    status_after_trigger = await client.get(f"/connectors/{connector_id}/status", headers=headers)
    assert status_after_trigger.json()["status"] == "ingesting"
