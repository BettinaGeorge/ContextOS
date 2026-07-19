from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.errors import NotFoundError
from src.core.auth import CurrentUser, get_current_user
from src.core.db import get_db
from src.repositories.workspace_repository import WorkspaceRepository
from src.services.answer_svc import AnswerService

router = APIRouter(tags=["ask"])


class AskRequest(BaseModel):
    question: str
    notion_doc_url: str | None = None


class CitationResponse(BaseModel):
    artifact_id: str
    source_url: str
    artifact_type: str
    origin: str


class AskResponse(BaseModel):
    answer: str
    abstained: bool
    citations: list[CitationResponse]


def get_answer_service(db: AsyncSession = Depends(get_db)) -> AnswerService:
    """A real dependency (not a bare instantiation inside the endpoint) so
    tests can override it via app.dependency_overrides with a fake
    Groq/Voyage-backed instance instead of hitting live APIs."""
    return AnswerService(db)


@router.post("/ask", response_model=AskResponse)
async def ask(
    body: AskRequest,
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    answer_service: AnswerService = Depends(get_answer_service),
) -> AskResponse:
    workspace = await WorkspaceRepository(db).get_by_owner(user.user_id)
    if workspace is None:
        raise NotFoundError(error="workspace_not_found")

    result = await answer_service.answer_question(workspace.id, body.question, body.notion_doc_url)
    return AskResponse(
        answer=result.answer,
        abstained=result.abstained,
        citations=[
            CitationResponse(
                artifact_id=c.artifact_id,
                source_url=c.source_url,
                artifact_type=c.artifact_type,
                origin=c.origin,
            )
            for c in result.citations
        ],
    )
