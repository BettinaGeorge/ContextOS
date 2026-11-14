"""FR-017 and FR-018 (specs/003): a connector has at most one active job, and a job that
was abandoned by a crashed worker cannot block it forever."""

from datetime import UTC, datetime, timedelta

import pytest

from src.models.connector import SourceSystem
from src.models.job import JobStatus
from src.models.workspace import Workspace
from src.repositories.connector_repository import ConnectorRepository
from src.services.ingestion_svc import IngestionService


async def _connector(db_session, owner: str):
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
async def test_second_trigger_returns_the_existing_queued_job(db_session):
    workspace, connector = await _connector(db_session, "single-active-queued")
    service = IngestionService(db_session)

    first = await service.trigger(workspace.id, connector.id)
    second = await service.trigger(workspace.id, connector.id)

    assert second.id == first.id


@pytest.mark.asyncio
async def test_trigger_returns_the_existing_running_job(db_session):
    workspace, connector = await _connector(db_session, "single-active-running")
    service = IngestionService(db_session)
    first = await service.trigger(workspace.id, connector.id)
    first.status = JobStatus.running
    first.started_at = datetime.now(UTC) - timedelta(minutes=59)
    await db_session.commit()

    second = await service.trigger(workspace.id, connector.id)

    assert second.id == first.id
    assert second.status == JobStatus.running


@pytest.mark.asyncio
async def test_trigger_returns_the_existing_job_that_is_waiting_to_retry(db_session):
    workspace, connector = await _connector(db_session, "single-active-retrying")
    service = IngestionService(db_session)
    first = await service.trigger(workspace.id, connector.id)
    first.attempts = 1
    first.next_attempt_at = datetime.now(UTC) + timedelta(seconds=30)
    await db_session.commit()

    second = await service.trigger(workspace.id, connector.id)

    assert second.id == first.id


@pytest.mark.asyncio
async def test_running_job_older_than_an_hour_is_marked_abandoned_and_replaced(db_session):
    workspace, connector = await _connector(db_session, "single-active-stale")
    service = IngestionService(db_session)
    stale = await service.trigger(workspace.id, connector.id)
    stale.status = JobStatus.running
    stale.started_at = datetime.now(UTC) - timedelta(minutes=61)
    await db_session.commit()

    replacement = await service.trigger(workspace.id, connector.id)

    await db_session.refresh(stale)
    assert stale.status == JobStatus.failed
    assert stale.error_message == "abandoned: worker stopped"
    assert replacement.id != stale.id
    assert replacement.status == JobStatus.queued
