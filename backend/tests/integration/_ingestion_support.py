"""Shared helpers for the idempotent-ingestion tests (specs/003, US2)."""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.connectors.base import NormalizedArtifact
from src.models.artifact import EMBEDDING_DIM, Artifact
from src.models.workspace import Workspace

ONE_FUNCTION = "def foo():\n    return 1\n"
TWO_FUNCTIONS = "def foo():\n    return 1\n\n\ndef bar():\n    return 2\n"
THREE_FUNCTIONS = TWO_FUNCTIONS + "\n\ndef baz():\n    return 3\n"


class CountingVoyage:
    """Fake embedding client that records every text it is asked to embed."""

    def __init__(self, fail_next_call: bool = False):
        self.batches: list[list[str]] = []
        self._fail_next_call = fail_next_call

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        self.batches.append(list(texts))
        if self._fail_next_call:
            self._fail_next_call = False
            raise RuntimeError("embedding service unavailable")
        return [[0.1] * EMBEDDING_DIM for _ in texts]

    @property
    def embedded_texts(self) -> list[str]:
        return [text for batch in self.batches for text in batch]


async def make_workspace(db_session: AsyncSession) -> Workspace:
    workspace = Workspace(owner_user_id=f"ingest-test-{uuid.uuid4()}", name="Ingest test")
    db_session.add(workspace)
    await db_session.commit()
    await db_session.refresh(workspace)
    return workspace


def source_file(path: str, content: str) -> NormalizedArtifact:
    return NormalizedArtifact(
        source_artifact_id=path,
        artifact_type="source_file",
        title=path,
        content=content,
        source_url=f"https://github.com/acme/widgets/blob/HEAD/{path}",
    )


def pull_request(number: int, content: str = "Implements a thing.") -> NormalizedArtifact:
    return NormalizedArtifact(
        source_artifact_id=str(number),
        artifact_type="pull_request",
        title=f"PR {number}",
        content=content,
        source_url=f"https://github.com/acme/widgets/pull/{number}",
    )


def notion_page(page_id: str, content: str) -> NormalizedArtifact:
    return NormalizedArtifact(
        source_artifact_id=page_id,
        artifact_type="document",
        title=f"Page {page_id}",
        content=content,
        source_url=f"https://notion.so/{page_id}",
    )


async def stored_artifacts(db_session: AsyncSession, workspace_id: uuid.UUID) -> list[Artifact]:
    db_session.expire_all()
    result = await db_session.execute(
        select(Artifact)
        .where(Artifact.workspace_id == workspace_id)
        .execution_options(populate_existing=True)
    )
    return list(result.scalars().all())


def snapshot(artifacts: list[Artifact]) -> set[tuple]:
    return {
        (str(a.artifact_type), a.source_artifact_id, a.checksum, a.title, a.content)
        for a in artifacts
    }
