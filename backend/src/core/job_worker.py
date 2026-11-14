import asyncio
import logging
from collections.abc import Awaitable, Callable

from sqlalchemy.ext.asyncio import AsyncSession

from src.connectors.base import ConnectorAuthError
from src.core.db import async_session_factory
from src.models.job import Job, JobType
from src.repositories.job_repository import JobRepository

logger = logging.getLogger("contextos.job_worker")

POLL_INTERVAL_SECONDS = 5

# Delay before retry number N is BACKOFF_SECONDS[N - 1]; the last attempt has no retry after it.
BACKOFF_SECONDS = (30, 120)
MAX_ATTEMPTS = len(BACKOFF_SECONDS) + 1


def is_permanent_failure(exc: Exception) -> bool:
    """A rejected credential or a missing connector will not fix itself, so retrying only
    delays the real error."""
    return isinstance(exc, (ConnectorAuthError, ValueError))

# research.md §1: an in-process asyncio poller, not a separate worker
# process/service — a dedicated Render worker is a paid resource and would
# break the $10 non-recurring budget the moment it's provisioned (ADR-001).
# Trade-off accepted: jobs stop progressing if this instance's free-tier
# process spins down from inactivity; acceptable at Phase 1's scale.
JobHandler = Callable[[Job, AsyncSession], Awaitable[None]]
_HANDLERS: dict[JobType, JobHandler] = {}


def register_handler(job_type: JobType, handler: JobHandler) -> None:
    """Called by ingestion_svc at import time (Phase 3) — job_worker itself
    has no dependency on connector-specific ingestion logic."""
    _HANDLERS[job_type] = handler


async def _process_one(session: AsyncSession) -> bool:
    repo = JobRepository(session)
    job = await repo.claim_oldest_queued()
    if job is None:
        return False

    handler = _HANDLERS.get(job.job_type)
    if handler is None:
        await repo.mark_failed(job, f"No handler registered for job_type={job.job_type}")
        return True

    try:
        await handler(job, session)
        await repo.mark_complete(job)
    except Exception as exc:  # noqa: BLE001 — job failures must never crash the worker loop
        logger.exception("Job %s failed (attempt %s)", job.id, job.attempts)
        if is_permanent_failure(exc) or job.attempts >= MAX_ATTEMPTS:
            await repo.mark_failed(job, str(exc))
        else:
            await repo.schedule_retry(job, str(exc), BACKOFF_SECONDS[job.attempts - 1])
    return True


async def run_worker_loop() -> None:
    while True:
        async with async_session_factory() as session:
            processed = await _process_one(session)
        if not processed:
            await asyncio.sleep(POLL_INTERVAL_SECONDS)


def start_job_worker() -> asyncio.Task:
    return asyncio.create_task(run_worker_loop())
