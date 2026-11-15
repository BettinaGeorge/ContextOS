from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.errors import ConflictError, NotFoundError
from src.core.auth import CurrentUser, get_current_user
from src.core.db import get_db
from src.core.job_worker import MAX_ATTEMPTS
from src.models.connector import SourceSystem
from src.models.job import Job, JobStatus
from src.repositories.connector_repository import ConnectorRepository
from src.repositories.job_repository import JobRepository
from src.repositories.workspace_repository import WorkspaceRepository

router = APIRouter(prefix="/connectors", tags=["connectors"])


class ConnectGithubRequest(BaseModel):
    repo: str
    auth_code_or_token: str


class ConnectNotionRequest(BaseModel):
    integration_token: str
    page_ids: list[str]


class ConnectorCreatedResponse(BaseModel):
    connector_id: str
    status: str


class ConnectorStatusResponse(BaseModel):
    connector_id: str
    source_system: str
    status: str
    last_ingested_at: str | None
    error_message: str | None
    ingestion_attempts: int | None = None
    max_attempts: int | None = None
    next_attempt_at: str | None = None


async def _get_owned_workspace(db: AsyncSession, user: CurrentUser):
    workspace = await WorkspaceRepository(db).get_by_owner(user.user_id)
    if workspace is None:
        raise NotFoundError(error="workspace_not_found", detail="Create a workspace first")
    return workspace


def _to_status_response(connector, latest_job: Job | None = None) -> ConnectorStatusResponse:
    waiting_to_retry = (
        latest_job is not None
        and latest_job.status == JobStatus.queued
        and latest_job.next_attempt_at is not None
    )
    return ConnectorStatusResponse(
        connector_id=str(connector.id),
        source_system=connector.source_system,
        status=connector.status,
        last_ingested_at=connector.last_ingested_at.isoformat()
        if connector.last_ingested_at
        else None,
        error_message=connector.error_message,
        ingestion_attempts=latest_job.attempts if latest_job else None,
        max_attempts=MAX_ATTEMPTS if latest_job else None,
        next_attempt_at=latest_job.next_attempt_at.isoformat() if waiting_to_retry else None,
    )


@router.post("/github", response_model=ConnectorCreatedResponse, status_code=202)
async def connect_github(
    body: ConnectGithubRequest,
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ConnectorCreatedResponse:
    workspace = await _get_owned_workspace(db, user)
    repo_conn = ConnectorRepository(db)
    if await repo_conn.get_by_workspace_and_source(workspace.id, SourceSystem.github):
        raise ConflictError(error="github_connector_already_exists")
    connector = await repo_conn.create(
        workspace_id=workspace.id,
        source_system=SourceSystem.github,
        raw_access_token=body.auth_code_or_token,
        external_resource_ref=body.repo,
    )
    return ConnectorCreatedResponse(connector_id=str(connector.id), status=connector.status)


@router.post("/notion", response_model=ConnectorCreatedResponse, status_code=202)
async def connect_notion(
    body: ConnectNotionRequest,
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ConnectorCreatedResponse:
    workspace = await _get_owned_workspace(db, user)
    repo_conn = ConnectorRepository(db)
    if await repo_conn.get_by_workspace_and_source(workspace.id, SourceSystem.notion):
        raise ConflictError(error="notion_connector_already_exists")
    connector = await repo_conn.create(
        workspace_id=workspace.id,
        source_system=SourceSystem.notion,
        raw_access_token=body.integration_token,
        external_resource_ref=",".join(body.page_ids),
    )
    return ConnectorCreatedResponse(connector_id=str(connector.id), status=connector.status)


@router.get("", response_model=list[ConnectorStatusResponse])
async def list_connectors(
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[ConnectorStatusResponse]:
    """Not in the original contracts/api.md — added for T056 (US3), the
    Ingestion status page needs a way to discover which connectors exist for
    the workspace before it can poll each one's status individually."""
    workspace = await _get_owned_workspace(db, user)
    connectors = await ConnectorRepository(db).list_by_workspace(workspace.id)
    jobs = JobRepository(db)
    return [
        _to_status_response(c, await jobs.latest_for_connector(workspace.id, c.id))
        for c in connectors
    ]


@router.get("/{connector_id}/status", response_model=ConnectorStatusResponse)
async def connector_status(
    connector_id: str,
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ConnectorStatusResponse:
    workspace = await _get_owned_workspace(db, user)
    connector = await ConnectorRepository(db).get_by_id(workspace.id, UUID(connector_id))
    if connector is None:
        raise NotFoundError(error="connector_not_found")
    latest_job = await JobRepository(db).latest_for_connector(workspace.id, connector.id)
    return _to_status_response(connector, latest_job)
