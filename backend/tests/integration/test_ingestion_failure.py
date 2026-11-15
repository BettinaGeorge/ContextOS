"""T054: forced ingestion failures surface a non-null error_message, and
auth-specific failures are distinguished (needs_reconnect) from generic
ones (failed) — per T055's ConnectorAuthError handling in ingestion_svc."""

import pytest

from src.connectors.base import ConnectorAuthError
from src.core.job_worker import MAX_ATTEMPTS
from src.models.connector import ConnectorStatus, SourceSystem
from src.models.job import JobType
from src.models.workspace import Workspace
from src.repositories.connector_repository import ConnectorRepository
from src.repositories.job_repository import JobRepository
from src.services import connector_svc as connector_svc_module
from src.services.ingestion_svc import _handle_ingestion_job


async def _make_workspace_and_connector(db_session, owner):
    workspace = Workspace(owner_user_id=owner, name="Test")
    db_session.add(workspace)
    await db_session.commit()
    await db_session.refresh(workspace)
    connector = await ConnectorRepository(db_session).create(
        workspace_id=workspace.id,
        source_system=SourceSystem.github,
        raw_access_token="fake-token",
        external_resource_ref="acme/widgets",
    )
    return workspace, connector


@pytest.mark.asyncio
async def test_auth_failure_sets_needs_reconnect_with_error_message(db_session, monkeypatch):
    workspace, connector = await _make_workspace_and_connector(db_session, "user-auth-fail")
    job = await JobRepository(db_session).enqueue(workspace.id, connector.id, JobType.ingest_github)

    async def auth_failing_ingest(self, workspace_id, connector):
        raise ConnectorAuthError("GitHub rejected the token (HTTP 401) for acme/widgets")

    monkeypatch.setattr(connector_svc_module.ConnectorService, "ingest", auth_failing_ingest)

    with pytest.raises(ConnectorAuthError):
        await _handle_ingestion_job(job, db_session)

    refreshed = await ConnectorRepository(db_session).get_by_id(workspace.id, connector.id)
    assert refreshed.status == ConnectorStatus.needs_reconnect
    assert refreshed.error_message is not None
    assert "401" in refreshed.error_message


@pytest.mark.asyncio
async def test_generic_failure_sets_failed_not_needs_reconnect(db_session, monkeypatch):
    workspace, connector = await _make_workspace_and_connector(db_session, "user-generic-fail")
    job = await JobRepository(db_session).enqueue(workspace.id, connector.id, JobType.ingest_github)

    async def network_failing_ingest(self, workspace_id, connector):
        raise TimeoutError("GitHub API request timed out")

    monkeypatch.setattr(connector_svc_module.ConnectorService, "ingest", network_failing_ingest)
    job.attempts = MAX_ATTEMPTS  # final attempt: the connector is marked failed only now

    with pytest.raises(TimeoutError):
        await _handle_ingestion_job(job, db_session)

    refreshed = await ConnectorRepository(db_session).get_by_id(workspace.id, connector.id)
    # A non-auth failure must NOT be labeled needs_reconnect — that would
    # incorrectly tell the user their token is bad when it isn't.
    assert refreshed.status == ConnectorStatus.failed
    assert refreshed.error_message is not None
    assert "timed out" in refreshed.error_message
