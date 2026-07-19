import re

from sqlalchemy.ext.asyncio import AsyncSession

from src.connectors.notion_connector import extract_github_links
from src.models.artifact import Artifact, ArtifactType
from src.models.relationship import RelationshipOrigin
from src.repositories.artifact_repository import ArtifactRepository
from src.repositories.relationship_repository import RelationshipRepository

# research.md §4: the other direction of the same convention — a Notion page
# URL referenced inside a GitHub PR/commit description.
NOTION_URL_RE = re.compile(r"https?://(?:www\.)?notion\.so/[\w./-]+")


class RelationshipService:
    """Deterministic (explicit) relationship extraction only — Constitution
    Principle II. No semantic/model-inferred matching happens here; that's
    retrieval_svc's fallback at answer time, and it's always labeled
    "inferred", never conflated with what this service produces."""

    def __init__(self, session: AsyncSession):
        self._session = session
        self._artifacts = ArtifactRepository(session)
        self._relationships = RelationshipRepository(session)

    async def extract_for_workspace(self, workspace_id) -> int:
        """Scans all currently-ingested artifacts in the workspace for the
        deterministic linking convention (PRD §4) and writes the
        relationships found. Returns the count created. Safe to re-run —
        idempotency at scale is a Phase 2 concern (PRD §10 open questions);
        Phase 1 accepts possible duplicate rows on re-ingestion."""
        documents = await self._artifacts.list_by_workspace(
            workspace_id, artifact_type=ArtifactType.document
        )
        pull_requests = await self._artifacts.list_by_workspace(
            workspace_id, artifact_type=ArtifactType.pull_request
        )
        commits = await self._artifacts.list_by_workspace(
            workspace_id, artifact_type=ArtifactType.commit
        )
        github_artifacts = pull_requests + commits

        created = 0
        for doc in documents:
            for url in extract_github_links(doc.content):
                target = _find_by_source_url(github_artifacts, url)
                if target is None:
                    continue
                await self._relationships.create(
                    workspace_id=workspace_id,
                    source_artifact_id=doc.id,
                    target_artifact_id=target.id,
                    relationship_type="references",
                    relationship_origin=RelationshipOrigin.explicit,
                    evidence=url,
                )
                created += 1

        for artifact in github_artifacts:
            for url in NOTION_URL_RE.findall(artifact.content):
                target = _find_by_source_url(documents, url)
                if target is None:
                    continue
                await self._relationships.create(
                    workspace_id=workspace_id,
                    source_artifact_id=artifact.id,
                    target_artifact_id=target.id,
                    relationship_type="references",
                    relationship_origin=RelationshipOrigin.explicit,
                    evidence=url,
                )
                created += 1

        return created


def _find_by_source_url(artifacts: list[Artifact], url: str) -> Artifact | None:
    # Exact match first, then prefix match — a Notion doc might link to a
    # PR/commit URL with a trailing slash or fragment the source_url doesn't have.
    for a in artifacts:
        if a.source_url == url:
            return a
    for a in artifacts:
        if url.startswith(a.source_url) or a.source_url.startswith(url):
            return a
    return None
