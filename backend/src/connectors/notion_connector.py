import re
from typing import Any

from notion_client import AsyncClient
from notion_client.errors import APIResponseError

from src.connectors.base import BaseConnector, ConnectorHealth, NormalizedArtifact

# Block types whose rich_text we extract as plain content (research.md §3:
# Notion pages are chunked by structural boundaries, not fixed-size splits —
# each block's text is one contributor to the page's overall content here;
# per-block chunking for retrieval happens in chunking.py, T036).
_TEXT_BLOCK_TYPES = {
    "paragraph",
    "heading_1",
    "heading_2",
    "heading_3",
    "bulleted_list_item",
    "numbered_list_item",
    "to_do",
    "quote",
    "callout",
    "code",
}

GITHUB_URL_RE = re.compile(r"https?://github\.com/[\w.-]+/[\w.-]+/(?:pull|commit)/[\w]+")


class NotionConnector(BaseConnector):
    """FR-003/FR-005: connects a Notion integration token scoped to a set of
    pages the user selected, and ingests each page's content."""

    def __init__(self, integration_token: str, page_ids: list[str]):
        self._token = integration_token
        self.page_ids = page_ids

    def _client(self) -> AsyncClient:
        return AsyncClient(auth=self._token)

    async def authenticate(self) -> None:
        client = self._client()
        try:
            await client.users.me()
        except APIResponseError as exc:
            raise ConnectionError(f"Notion authentication failed: {exc}") from exc
        finally:
            await client.aclose()

    async def health_check(self) -> ConnectorHealth:
        client = self._client()
        try:
            await client.users.me()
            return ConnectorHealth(healthy=True)
        except APIResponseError as exc:
            return ConnectorHealth(healthy=False, detail=str(exc))
        finally:
            await client.aclose()

    async def ingest_full(self) -> list[NormalizedArtifact]:
        client = self._client()
        try:
            artifacts = []
            for page_id in self.page_ids:
                page = await client.pages.retrieve(page_id=page_id)
                blocks = await self._fetch_all_blocks(client, page_id)
                artifacts.append(self.normalize_artifact({"page": page, "blocks": blocks}))
            return artifacts
        finally:
            await client.aclose()

    async def _fetch_all_blocks(self, client: AsyncClient, block_id: str) -> list[dict[str, Any]]:
        blocks: list[dict[str, Any]] = []
        cursor = None
        while True:
            kwargs = {"block_id": block_id}
            if cursor:
                kwargs["start_cursor"] = cursor
            resp = await client.blocks.children.list(**kwargs)
            for block in resp["results"]:
                blocks.append(block)
                if block.get("has_children"):
                    blocks.extend(await self._fetch_all_blocks(client, block["id"]))
            if not resp.get("has_more"):
                break
            cursor = resp.get("next_cursor")
        return blocks

    def normalize_artifact(self, raw: dict[str, Any]) -> NormalizedArtifact:
        page = raw["page"]
        blocks = raw["blocks"]
        title = _extract_page_title(page)
        content = "\n\n".join(_block_text(b) for b in blocks if _block_text(b))
        return NormalizedArtifact(
            source_artifact_id=page["id"],
            artifact_type="document",
            title=title,
            content=content,
            source_url=page.get("url", ""),
            created_at=page.get("created_time"),
            updated_at=page.get("last_edited_time"),
        )

    async def normalize_relationship(
        self, artifacts: list[NormalizedArtifact]
    ) -> list[tuple[str, str, str]]:
        # Same-connector relationships aren't meaningful for a flat set of
        # independently-selected pages in Phase 1 (no parent/child page
        # ingestion yet). Cross-connector linking is relationship_svc's job.
        return []


def _extract_page_title(page: dict[str, Any]) -> str:
    properties = page.get("properties", {})
    for prop in properties.values():
        if prop.get("type") == "title":
            title_parts = prop.get("title", [])
            text = "".join(t.get("plain_text", "") for t in title_parts)
            if text:
                return text
    return "Untitled"


def _block_text(block: dict[str, Any]) -> str:
    block_type = block.get("type")
    if block_type not in _TEXT_BLOCK_TYPES:
        return ""
    rich_text = block.get(block_type, {}).get("rich_text", [])
    return "".join(t.get("plain_text", "") for t in rich_text)


def extract_github_links(text: str) -> list[str]:
    """Used by relationship_svc (T038) for the Notion side of deterministic
    link extraction (research.md §4)."""
    return GITHUB_URL_RE.findall(text)
