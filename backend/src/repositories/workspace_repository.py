import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.workspace import Workspace


class WorkspaceRepository:
    def __init__(self, session: AsyncSession):
        self._session = session

    async def get_by_owner(self, owner_user_id: str) -> Workspace | None:
        result = await self._session.execute(
            select(Workspace).where(Workspace.owner_user_id == owner_user_id)
        )
        return result.scalar_one_or_none()

    async def get_by_id(self, workspace_id: uuid.UUID) -> Workspace | None:
        result = await self._session.execute(select(Workspace).where(Workspace.id == workspace_id))
        return result.scalar_one_or_none()

    async def create(self, owner_user_id: str, name: str) -> Workspace:
        workspace = Workspace(owner_user_id=owner_user_id, name=name)
        self._session.add(workspace)
        await self._session.commit()
        await self._session.refresh(workspace)
        return workspace
