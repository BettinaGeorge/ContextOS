from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.errors import NotFoundError
from src.core.auth import CurrentUser, get_current_user
from src.core.db import get_db
from src.repositories.workspace_repository import WorkspaceRepository
from src.services.workspace_svc import WorkspaceService

router = APIRouter(prefix="/workspaces", tags=["workspaces"])


class CreateWorkspaceRequest(BaseModel):
    name: str


class WorkspaceResponse(BaseModel):
    id: str
    name: str
    created_at: str


@router.post("", response_model=WorkspaceResponse, status_code=201)
async def create_workspace(
    body: CreateWorkspaceRequest,
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> WorkspaceResponse:
    workspace = await WorkspaceService(db).create_workspace(user.user_id, body.name)
    return WorkspaceResponse(
        id=str(workspace.id), name=workspace.name, created_at=workspace.created_at.isoformat()
    )


@router.get("/{workspace_id}", response_model=WorkspaceResponse)
async def get_workspace(
    workspace_id: str,
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> WorkspaceResponse:
    workspace = await WorkspaceRepository(db).get_by_id(UUID(workspace_id))
    if workspace is None or workspace.owner_user_id != user.user_id:
        raise NotFoundError(error="workspace_not_found")
    return WorkspaceResponse(
        id=str(workspace.id), name=workspace.name, created_at=workspace.created_at.isoformat()
    )
