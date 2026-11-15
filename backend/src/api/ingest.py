from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.errors import NotFoundError
from src.core.auth import CurrentUser, get_current_user
from src.core.db import get_db
from src.core.job_worker import MAX_ATTEMPTS
from src.models.job import Job
from src.repositories.job_repository import JobRepository
from src.repositories.workspace_repository import WorkspaceRepository
from src.services.ingestion_svc import IngestionService

router = APIRouter(prefix="/ingest", tags=["ingest"])


class IngestJobResponse(BaseModel):
    job_id: str
    status: str
    error_message: str | None = None
    attempts: int = 0
    max_attempts: int = MAX_ATTEMPTS
    next_attempt_at: str | None = None


def _to_job_response(job: Job) -> IngestJobResponse:
    return IngestJobResponse(
        job_id=str(job.id),
        status=job.status,
        error_message=job.error_message,
        attempts=job.attempts,
        max_attempts=MAX_ATTEMPTS,
        next_attempt_at=job.next_attempt_at.isoformat() if job.next_attempt_at else None,
    )


async def _get_owned_workspace(db: AsyncSession, user: CurrentUser):
    workspace = await WorkspaceRepository(db).get_by_owner(user.user_id)
    if workspace is None:
        raise NotFoundError(error="workspace_not_found")
    return workspace


@router.post("/{connector_id}", response_model=IngestJobResponse, status_code=202)
async def trigger_ingest(
    connector_id: str,
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> IngestJobResponse:
    workspace = await _get_owned_workspace(db, user)
    try:
        job = await IngestionService(db).trigger(workspace.id, UUID(connector_id))
    except ValueError as exc:
        raise NotFoundError(error="connector_not_found", detail=str(exc)) from exc
    return _to_job_response(job)


@router.get("/{job_id}/status", response_model=IngestJobResponse)
async def ingest_job_status(
    job_id: str,
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> IngestJobResponse:
    workspace = await _get_owned_workspace(db, user)
    job = await JobRepository(db).get_by_id(workspace.id, UUID(job_id))
    if job is None:
        raise NotFoundError(error="job_not_found")
    return _to_job_response(job)
