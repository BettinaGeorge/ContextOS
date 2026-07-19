from sqlalchemy.ext.asyncio import AsyncSession

from src.api.errors import ConflictError
from src.models.workspace import Workspace
from src.repositories.workspace_repository import WorkspaceRepository


class WorkspaceService:
    def __init__(self, session: AsyncSession):
        self._repo = WorkspaceRepository(session)

    async def create_workspace(self, owner_user_id: str, name: str) -> Workspace:
        # FR-001 / spec.md: exactly one workspace per user in Phase 1.
        existing = await self._repo.get_by_owner(owner_user_id)
        if existing is not None:
            raise ConflictError(
                error="workspace_already_exists",
                detail=f"Workspace {existing.id} already exists for this user",
            )
        return await self._repo.create(owner_user_id=owner_user_id, name=name)
