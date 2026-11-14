import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import or_, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.job import Job, JobStatus, JobType


# A job that has been "running" this long was almost certainly left behind by a crashed
# worker. Without this, the one-active-job-per-connector rule would block the connector
# forever. A healthy job swept by mistake is harmless: ingestion is idempotent.
STALE_RUNNING_AFTER = timedelta(minutes=60)


class JobRepository:
    def __init__(self, session: AsyncSession):
        self._session = session

    async def enqueue(
        self, workspace_id: uuid.UUID, connector_id: uuid.UUID, job_type: JobType
    ) -> Job:
        job, _ = await self.enqueue_or_get(workspace_id, connector_id, job_type)
        return job

    async def enqueue_or_get(
        self, workspace_id: uuid.UUID, connector_id: uuid.UUID, job_type: JobType
    ) -> tuple[Job, bool]:
        """Creates a job unless the connector already has a queued or running one, in which
        case that job is returned. The second value says whether a job was created."""
        await self._mark_abandoned(connector_id)
        job = Job(workspace_id=workspace_id, connector_id=connector_id, job_type=job_type)
        self._session.add(job)
        try:
            await self._session.commit()
        except IntegrityError:
            await self._session.rollback()
            existing = await self._active_job(connector_id)
            if existing is None:
                raise
            return existing, False
        await self._session.refresh(job)
        return job, True

    async def _active_job(self, connector_id: uuid.UUID) -> Job | None:
        result = await self._session.execute(
            select(Job)
            .where(
                Job.connector_id == connector_id,
                Job.status.in_([JobStatus.queued, JobStatus.running]),
            )
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def _mark_abandoned(self, connector_id: uuid.UUID) -> None:
        now = datetime.now(UTC)
        await self._session.execute(
            update(Job)
            .where(
                Job.connector_id == connector_id,
                Job.status == JobStatus.running,
                Job.started_at < now - STALE_RUNNING_AFTER,
            )
            .values(
                status=JobStatus.failed,
                error_message="abandoned: worker stopped",
                completed_at=now,
            )
        )
        await self._session.commit()

    async def latest_for_connector(
        self, workspace_id: uuid.UUID, connector_id: uuid.UUID
    ) -> Job | None:
        result = await self._session.execute(
            select(Job)
            .where(Job.workspace_id == workspace_id, Job.connector_id == connector_id)
            .order_by(Job.created_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def get_by_id(self, workspace_id: uuid.UUID, job_id: uuid.UUID) -> Job | None:
        result = await self._session.execute(
            select(Job).where(Job.workspace_id == workspace_id, Job.id == job_id)
        )
        return result.scalar_one_or_none()

    async def claim_oldest_queued(self) -> Job | None:
        """Used by the in-process job worker (core/job_worker.py, T022) to pick
        the next job to run. Not workspace-scoped by design — the worker
        processes jobs across all workspaces, one at a time.

        FOR UPDATE SKIP LOCKED makes this safe with more than one worker: a row
        another worker is claiming is skipped, not waited for, so no job is
        claimed twice. The claim and the status change commit together."""
        result = await self._session.execute(
            select(Job)
            .where(
                Job.status == JobStatus.queued,
                or_(Job.next_attempt_at.is_(None), Job.next_attempt_at <= datetime.now(UTC)),
            )
            .order_by(Job.created_at)
            .limit(1)
            .with_for_update(skip_locked=True)
        )
        job = result.scalar_one_or_none()
        if job is None:
            return None
        job.status = JobStatus.running
        job.attempts += 1
        job.started_at = datetime.now(UTC)
        await self._session.commit()
        await self._session.refresh(job)
        return job

    async def mark_complete(self, job: Job) -> Job:
        job.status = JobStatus.complete
        job.completed_at = datetime.now(UTC)
        await self._session.commit()
        await self._session.refresh(job)
        return job

    async def schedule_retry(self, job: Job, error_message: str, delay_seconds: int) -> Job:
        """Puts a failed attempt back in the queue for later; the error stays visible."""
        job.status = JobStatus.queued
        job.error_message = error_message
        job.next_attempt_at = datetime.now(UTC) + timedelta(seconds=delay_seconds)
        await self._session.commit()
        await self._session.refresh(job)
        return job

    async def mark_failed(self, job: Job, error_message: str) -> Job:
        job.status = JobStatus.failed
        job.error_message = error_message
        job.completed_at = datetime.now(UTC)
        await self._session.commit()
        await self._session.refresh(job)
        return job
