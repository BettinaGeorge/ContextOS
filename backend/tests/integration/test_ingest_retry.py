"""SC-003 and SC-005 (specs/003): transient failures retry with growing delays, the
final error stays visible, and a rejected credential is not retried.

Drives the real worker step (`_process_one`) against a fake source. Time is controlled
by rewriting `next_attempt_at`, so nothing sleeps."""

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import update

from src.connectors.base import ConnectorAuthError
from src.core.job_worker import BACKOFF_SECONDS, MAX_ATTEMPTS, _process_one
from src.models.connector import ConnectorStatus, SourceSystem
from src.models.job import Job, JobStatus, JobType
from src.models.workspace import Workspace
from src.repositories.connector_repository import ConnectorRepository
from src.repositories.job_repository import JobRepository
from src.services import connector_svc as connector_svc_module
from src.services import relationship_svc as relationship_svc_module
from src.services.ingestion_svc import IngestionService  # noqa: F401 — registers the handler


@pytest.fixture(autouse=True)
async def _no_other_queued_jobs(db_session):
    """The worker claims the oldest queued job in the whole database; park leftovers from
    other tests so each test here only ever claims its own job."""
    await db_session.execute(
        update(Job)
        .where(Job.status == JobStatus.queued)
        .values(status=JobStatus.failed, error_message="parked by retry test")
    )
    await db_session.commit()


async def _connector_with_job(db_session, owner: str):
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
    job = await JobRepository(db_session).enqueue(workspace.id, connector.id, JobType.ingest_github)
    return workspace, connector, job


def _fake_source(monkeypatch, outcomes: list):
    """Each call to ingest consumes one outcome: an exception to raise, or None to succeed."""
    calls = {"count": 0}

    async def ingest(self, workspace_id, connector):
        outcome = outcomes[min(calls["count"], len(outcomes) - 1)]
        calls["count"] += 1
        if outcome is not None:
            raise outcome
        return 0

    async def extract(self, workspace_id):
        return 0

    monkeypatch.setattr(connector_svc_module.ConnectorService, "ingest", ingest)
    monkeypatch.setattr(
        relationship_svc_module.RelationshipService, "extract_for_workspace", extract
    )
    return calls


async def _make_due(db_session, job):
    due = datetime.now(UTC) - timedelta(seconds=1)
    await db_session.execute(update(Job).where(Job.id == job.id).values(next_attempt_at=due))
    await db_session.commit()


async def _run_attempt(db_session, job, connector):
    processed = await _process_one(db_session)
    await db_session.refresh(job)
    await db_session.refresh(connector)
    return processed


@pytest.mark.asyncio
async def test_fails_twice_then_succeeds_without_the_connector_ever_failing(
    db_session, monkeypatch
):
    _, connector, job = await _connector_with_job(db_session, "retry-then-succeed")
    _fake_source(monkeypatch, [RuntimeError("boom 1"), RuntimeError("boom 2"), None])
    connector_statuses = []

    for _ in range(MAX_ATTEMPTS):
        assert await _run_attempt(db_session, job, connector) is True
        connector_statuses.append(connector.status)
        if job.status == JobStatus.queued:
            await _make_due(db_session, job)

    assert job.status == JobStatus.complete
    assert job.attempts == 3
    assert ConnectorStatus.failed not in connector_statuses
    assert connector.status == ConnectorStatus.complete


@pytest.mark.asyncio
async def test_while_retries_remain_job_is_queued_for_later_and_connector_is_ingesting(
    db_session, monkeypatch
):
    _, connector, job = await _connector_with_job(db_session, "retry-waiting")
    _fake_source(monkeypatch, [RuntimeError("temporary outage")])

    await _run_attempt(db_session, job, connector)

    assert job.status == JobStatus.queued
    assert job.attempts == 1
    assert job.next_attempt_at is not None and job.next_attempt_at > datetime.now(UTC)
    assert connector.status == ConnectorStatus.ingesting
    assert connector.error_message == "temporary outage"
    assert await _process_one(db_session) is False


@pytest.mark.asyncio
async def test_always_failing_ends_failed_after_exactly_three_attempts_with_last_error(
    db_session, monkeypatch
):
    _, connector, job = await _connector_with_job(db_session, "retry-exhausted")
    calls = _fake_source(
        monkeypatch, [RuntimeError("boom 1"), RuntimeError("boom 2"), RuntimeError("boom 3")]
    )

    for _ in range(MAX_ATTEMPTS):
        await _run_attempt(db_session, job, connector)
        if job.status == JobStatus.queued:
            await _make_due(db_session, job)

    assert calls["count"] == MAX_ATTEMPTS
    assert job.status == JobStatus.failed
    assert job.attempts == MAX_ATTEMPTS
    assert job.error_message == "boom 3"
    assert connector.status == ConnectorStatus.failed
    assert connector.error_message == "boom 3"
    assert await _process_one(db_session) is False


@pytest.mark.asyncio
async def test_delays_between_attempts_increase(db_session, monkeypatch):
    _, connector, job = await _connector_with_job(db_session, "retry-delays")
    _fake_source(monkeypatch, [RuntimeError("boom")])
    delays = []

    for _ in range(MAX_ATTEMPTS - 1):
        await _run_attempt(db_session, job, connector)
        delays.append((job.next_attempt_at - datetime.now(UTC)).total_seconds())
        await _make_due(db_session, job)

    assert BACKOFF_SECONDS[0] - 5 <= delays[0] <= BACKOFF_SECONDS[0]
    assert BACKOFF_SECONDS[1] - 5 <= delays[1] <= BACKOFF_SECONDS[1]
    assert delays[1] > delays[0]


@pytest.mark.asyncio
async def test_credential_rejection_is_not_retried(db_session, monkeypatch):
    _, connector, job = await _connector_with_job(db_session, "retry-auth")
    calls = _fake_source(monkeypatch, [ConnectorAuthError("GitHub rejected the token (HTTP 401)")])

    await _run_attempt(db_session, job, connector)

    assert job.status == JobStatus.failed
    assert job.attempts == 1
    assert connector.status == ConnectorStatus.needs_reconnect
    assert await _process_one(db_session) is False
    assert calls["count"] == 1
