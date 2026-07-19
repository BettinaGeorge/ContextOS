from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.auth import CurrentUser, get_current_user
from src.core.db import get_db
from src.repositories.workspace_repository import WorkspaceRepository

router = APIRouter(tags=["auth"])


class MeResponse(BaseModel):
    user_id: str
    workspace_id: str | None


@router.get("/me", response_model=MeResponse)
async def get_me(
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> MeResponse:
    workspace = await WorkspaceRepository(db).get_by_owner(user.user_id)
    return MeResponse(user_id=user.user_id, workspace_id=str(workspace.id) if workspace else None)
