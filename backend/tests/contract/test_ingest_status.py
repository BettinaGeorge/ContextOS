"""contracts/api.md (specs/003): the new retry fields are additive and null when there
has never been a job."""

from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest

from src.repositories.job_repository import JobRepository

EXISTING_CONNECTOR_FIELDS = {
    "connector_id",
    "source_system",
    "status",
    "last_ingested_at",
    "error_message",
}


async def _workspace_and_connector(client, make_jwt):
    headers = {"Authorization": f"Bearer {make_jwt()}"}
    workspace = await client.post("/workspaces", json={"name": "Test"}, headers=headers)
    assert workspace.status_code == 201
    connector = await client.post(
        "/connectors/github",
        json={"repo": "acme/widgets", "auth_code_or_token": "fake"},
        headers=headers,
    )
    assert connector.status_code == 202
    return headers, workspace.json()["id"], connector.json()["connector_id"]


@pytest.mark.asyncio
async def test_connector_that_never_had_a_job_has_null_retry_fields(client, make_jwt):
    headers, _, connector_id = await _workspace_and_connector(client, make_jwt)

    body = (await client.get(f"/connectors/{connector_id}/status", headers=headers)).json()

    assert EXISTING_CONNECTOR_FIELDS <= body.keys()
    assert body["ingestion_attempts"] is None
    assert body["max_attempts"] is None
    assert body["next_attempt_at"] is None


@pytest.mark.asyncio
async def test_job_response_carries_attempt_fields(client, make_jwt):
    headers, _, connector_id = await _workspace_and_connector(client, make_jwt)

    triggered = await client.post(f"/ingest/{connector_id}", headers=headers)
    assert triggered.status_code == 202
    body = triggered.json()

    assert {"job_id", "status", "error_message"} <= body.keys()
    assert body["attempts"] == 0
    assert body["max_attempts"] == 3
    assert body["next_attempt_at"] is None

    status = (await client.get(f"/ingest/{body['job_id']}/status", headers=headers)).json()
    assert status["attempts"] == 0 and status["max_attempts"] == 3


@pytest.mark.asyncio
async def test_connector_status_reflects_a_job_waiting_to_retry(client, make_jwt, db_session):
    headers, workspace_id, connector_id = await _workspace_and_connector(client, make_jwt)
    job_id = (await client.post(f"/ingest/{connector_id}", headers=headers)).json()["job_id"]
    job = await JobRepository(db_session).get_by_id(UUID(workspace_id), UUID(job_id))
    retry_at = datetime.now(UTC) + timedelta(seconds=30)
    job.attempts = 1
    job.next_attempt_at = retry_at
    job.error_message = "temporary outage"
    await db_session.commit()

    connector = (await client.get(f"/connectors/{connector_id}/status", headers=headers)).json()
    listed = (await client.get("/connectors", headers=headers)).json()[0]
    job_status = (await client.get(f"/ingest/{job_id}/status", headers=headers)).json()

    for body in (connector, listed):
        assert body["status"] == "ingesting"
        assert body["ingestion_attempts"] == 1
        assert body["max_attempts"] == 3
        assert body["next_attempt_at"] is not None
    assert job_status["attempts"] == 1
    assert job_status["status"] == "queued"
    assert job_status["error_message"] == "temporary outage"
    assert job_status["next_attempt_at"] is not None
