"""SC-004 (specs/003): with two workers, every queued job is claimed exactly once.

Two workers are two sessions claiming concurrently from the same database."""

import asyncio

import pytest
from sqlalchemy import update

from src.core.db import async_session_factory
from src.models.connector import SourceSystem
from src.models.job import Job, JobStatus, JobType
from src.models.workspace import Workspace
from src.repositories.connector_repository import ConnectorRepository
from src.repositories.job_repository import JobRepository

JOB_COUNT = 20
ROUNDS = 3


@pytest.fixture(autouse=True)
async def _no_other_queued_jobs(db_session):
    """Park jobs left queued by other tests so only this test's jobs are claimable."""
    await db_session.execute(
        update(Job)
        .where(Job.status == JobStatus.queued)
        .values(status=JobStatus.failed, error_message="parked by claiming test")
    )
    await db_session.commit()


async def _connectors(db_session, count: int):
    """One connector per job, because a connector may only have one active job."""
    made = []
    for index in range(count):
        workspace = Workspace(owner_user_id=f"claiming-test-{index}", name="Test")
        db_session.add(workspace)
        await db_session.commit()
        await db_session.refresh(workspace)
        connector = await ConnectorRepository(db_session).create(
            workspace_id=workspace.id,
            source_system=SourceSystem.github,
            raw_access_token="fake-token",
            external_resource_ref="acme/widgets",
        )
        made.append((workspace.id, connector.id))
    return made


async def _worker(claimed: list) -> None:
    async with async_session_factory() as session:
        repo = JobRepository(session)
        while (job := await repo.claim_oldest_queued()) is not None:
            claimed.append(job.id)
            await asyncio.sleep(0)
            await repo.mark_complete(job)


@pytest.mark.asyncio
async def test_two_workers_claim_every_job_exactly_once(db_session):
    connectors = await _connectors(db_session, JOB_COUNT)

    for _ in range(ROUNDS):
        queued_ids = set()
        for workspace_id, connector_id in connectors:
            job = await JobRepository(db_session).enqueue(
                workspace_id, connector_id, JobType.ingest_github
            )
            queued_ids.add(job.id)

        worker_a: list = []
        worker_b: list = []
        await asyncio.gather(_worker(worker_a), _worker(worker_b))

        all_claims = worker_a + worker_b
        assert len(all_claims) == len(set(all_claims)), "a job was claimed twice"
        assert set(all_claims) == queued_ids


@pytest.mark.asyncio
async def test_one_queued_job_and_two_simultaneous_claims_gives_one_winner(db_session):
    [(workspace_id, connector_id)] = await _connectors(db_session, 1)
    await JobRepository(db_session).enqueue(workspace_id, connector_id, JobType.ingest_github)

    async def claim():
        async with async_session_factory() as session:
            return await JobRepository(session).claim_oldest_queued()

    results = await asyncio.gather(claim(), claim())

    assert sum(result is not None for result in results) == 1
    assert sum(result is None for result in results) == 1


@pytest.mark.asyncio
async def test_a_running_job_is_never_claimed_again(db_session):
    [(workspace_id, connector_id)] = await _connectors(db_session, 1)
    await JobRepository(db_session).enqueue(workspace_id, connector_id, JobType.ingest_github)

    async with async_session_factory() as first, async_session_factory() as second:
        claimed = await JobRepository(first).claim_oldest_queued()
        assert claimed is not None and claimed.status == JobStatus.running

        assert await JobRepository(second).claim_oldest_queued() is None
