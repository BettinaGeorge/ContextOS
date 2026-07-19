import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.job import Job, JobStatus, JobType


class JobRepository:
    def __init__(self, session: AsyncSession):
        self._session = session

    async def enqueue(
        self, workspace_id: uuid.UUID, connector_id: uuid.UUID, job_type: JobType
    ) -> Job:
        job = Job(workspace_id=workspace_id, connector_id=connector_id, job_type=job_type)
        self._session.add(job)
        await self._session.commit()
        await self._session.refresh(job)
        return job

    async def get_by_id(self, workspace_id: uuid.UUID, job_id: uuid.UUID) -> Job | None:
        result = await self._session.execute(
            select(Job).where(Job.workspace_id == workspace_id, Job.id == job_id)
        )
        return result.scalar_one_or_none()

    async def claim_oldest_queued(self) -> Job | None:
        """Used by the in-process job worker (core/job_worker.py, T022) to pick
        the next job to run. Not workspace-scoped by design — the worker
        processes jobs across all workspaces, one at a time."""
        result = await self._session.execute(
            select(Job).where(Job.status == JobStatus.queued).order_by(Job.created_at).limit(1)
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

    async def mark_failed(self, job: Job, error_message: str) -> Job:
        job.status = JobStatus.failed
        job.error_message = error_message
        job.completed_at = datetime.now(UTC)
        await self._session.commit()
        await self._session.refresh(job)
        return job
