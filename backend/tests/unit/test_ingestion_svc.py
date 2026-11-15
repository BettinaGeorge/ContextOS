import pytest

from src.core.job_worker import MAX_ATTEMPTS
from src.models.connector import ConnectorStatus, SourceSystem
from src.models.job import JobStatus, JobType
from src.models.workspace import Workspace
from src.repositories.connector_repository import ConnectorRepository
from src.repositories.job_repository import JobRepository
from src.services import connector_svc as connector_svc_module
from src.services import relationship_svc as relationship_svc_module
from src.services.ingestion_svc import IngestionService, _handle_ingestion_job


async def _make_workspace_and_connector(db_session, owner="test-user"):
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
async def test_trigger_enqueues_job_and_marks_connector_ingesting(db_session):
    workspace, connector = await _make_workspace_and_connector(db_session)

    job = await IngestionService(db_session).trigger(workspace.id, connector.id)

    assert job.status == JobStatus.queued
    assert job.job_type == JobType.ingest_github

    refreshed = await ConnectorRepository(db_session).get_by_id(workspace.id, connector.id)
    assert refreshed.status == ConnectorStatus.ingesting


@pytest.mark.asyncio
async def test_handle_ingestion_job_marks_connector_complete_on_success(db_session, monkeypatch):
    workspace, connector = await _make_workspace_and_connector(db_session, owner="user-2")
    job = await JobRepository(db_session).enqueue(workspace.id, connector.id, JobType.ingest_github)

    async def fake_ingest(self, workspace_id, connector):
        return 0

    async def fake_extract(self, workspace_id):
        return 0

    monkeypatch.setattr(connector_svc_module.ConnectorService, "ingest", fake_ingest)
    monkeypatch.setattr(
        relationship_svc_module.RelationshipService, "extract_for_workspace", fake_extract
    )

    await _handle_ingestion_job(job, db_session)

    refreshed = await ConnectorRepository(db_session).get_by_id(workspace.id, connector.id)
    assert refreshed.status == ConnectorStatus.complete
    assert refreshed.last_ingested_at is not None


@pytest.mark.asyncio
async def test_handle_ingestion_job_marks_connector_failed_on_error(db_session, monkeypatch):
    workspace, connector = await _make_workspace_and_connector(db_session, owner="user-3")
    job = await JobRepository(db_session).enqueue(workspace.id, connector.id, JobType.ingest_github)

    async def failing_ingest(self, workspace_id, connector):
        raise RuntimeError("GitHub API is down")

    monkeypatch.setattr(connector_svc_module.ConnectorService, "ingest", failing_ingest)
    job.attempts = MAX_ATTEMPTS  # final attempt: the connector is marked failed only now

    with pytest.raises(RuntimeError):
        await _handle_ingestion_job(job, db_session)

    refreshed = await ConnectorRepository(db_session).get_by_id(workspace.id, connector.id)
    assert refreshed.status == ConnectorStatus.failed
    assert refreshed.error_message == "GitHub API is down"


@pytest.mark.asyncio
async def test_handle_ingestion_job_keeps_connector_ingesting_when_retries_remain(
    db_session, monkeypatch
):
    workspace, connector = await _make_workspace_and_connector(db_session, owner="user-4")
    job = await JobRepository(db_session).enqueue(workspace.id, connector.id, JobType.ingest_github)
    job.attempts = 1

    async def failing_ingest(self, workspace_id, connector):
        raise RuntimeError("GitHub API is down")

    monkeypatch.setattr(connector_svc_module.ConnectorService, "ingest", failing_ingest)

    with pytest.raises(RuntimeError):
        await _handle_ingestion_job(job, db_session)

    refreshed = await ConnectorRepository(db_session).get_by_id(workspace.id, connector.id)
    assert refreshed.status == ConnectorStatus.ingesting
    assert refreshed.error_message == "GitHub API is down"
