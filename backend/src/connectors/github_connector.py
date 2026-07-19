import base64
import binascii
from datetime import datetime
from typing import Any

import httpx

from src.connectors.base import (
    BaseConnector,
    ConnectorAuthError,
    ConnectorHealth,
    NormalizedArtifact,
)

GITHUB_API_BASE = "https://api.github.com"

# Keeps ingestion tractable for a Phase 1 demo repo without a real size
# limit/pagination strategy (PRD §4 explicitly scopes this to one small
# repo) — revisit if a larger repo is ever connected.
MAX_FILES = 200
SKIP_EXTENSIONS = {
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".ico",
    ".svg",
    ".woff",
    ".woff2",
    ".ttf",
    ".zip",
    ".tar",
    ".gz",
    ".pdf",
    ".lock",
}


class GitHubConnector(BaseConnector):
    """FR-002/FR-004: connects one GitHub repository, ingests files, PRs,
    commits, and issues. Contributor data (also named in FR-004) is used to
    enrich author fields rather than stored as its own artifact — the
    canonical artifact_type enum (data-model.md) has no "contributor" slot,
    and adding one wasn't a decision made during planning."""

    def __init__(self, access_token: str, owner: str, repo: str):
        self._token = access_token
        self.owner = owner
        self.repo = repo

    def _client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(
            base_url=GITHUB_API_BASE,
            headers={
                "Authorization": f"Bearer {self._token}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
            },
            timeout=30.0,
        )

    async def authenticate(self) -> None:
        async with self._client() as client:
            response = await client.get(f"/repos/{self.owner}/{self.repo}")
            if response.status_code in (401, 403):
                raise ConnectorAuthError(
                    f"GitHub rejected the token (HTTP {response.status_code}) for "
                    f"{self.owner}/{self.repo}"
                )
            response.raise_for_status()

    async def health_check(self) -> ConnectorHealth:
        try:
            async with self._client() as client:
                response = await client.get(f"/repos/{self.owner}/{self.repo}")
            if response.status_code == 200:
                return ConnectorHealth(healthy=True)
            return ConnectorHealth(healthy=False, detail=f"HTTP {response.status_code}")
        except httpx.HTTPError as exc:
            return ConnectorHealth(healthy=False, detail=str(exc))

    async def ingest_full(self) -> list[NormalizedArtifact]:
        async with self._client() as client:
            artifacts: list[NormalizedArtifact] = []
            artifacts += await self._ingest_files(client)
            artifacts += await self._ingest_pull_requests(client)
            artifacts += await self._ingest_commits(client)
            artifacts += await self._ingest_issues(client)
            return artifacts

    async def _ingest_files(self, client: httpx.AsyncClient) -> list[NormalizedArtifact]:
        repo_resp = await client.get(f"/repos/{self.owner}/{self.repo}")
        repo_resp.raise_for_status()
        default_branch = repo_resp.json()["default_branch"]

        tree_resp = await client.get(
            f"/repos/{self.owner}/{self.repo}/git/trees/{default_branch}",
            params={"recursive": "1"},
        )
        tree_resp.raise_for_status()
        blobs = [
            item
            for item in tree_resp.json().get("tree", [])
            if item["type"] == "blob"
            and not any(item["path"].endswith(ext) for ext in SKIP_EXTENSIONS)
        ][:MAX_FILES]

        artifacts = []
        for blob in blobs:
            content_resp = await client.get(
                f"/repos/{self.owner}/{self.repo}/contents/{blob['path']}",
                params={"ref": default_branch},
            )
            if content_resp.status_code != 200:
                continue
            data = content_resp.json()
            if data.get("encoding") != "base64":
                continue
            try:
                text = base64.b64decode(data["content"]).decode("utf-8")
            except (UnicodeDecodeError, binascii.Error):
                continue  # binary file slipped past the extension filter
            artifacts.append(
                self.normalize_artifact(
                    {"type": "file", "path": blob["path"], "content": text, "sha": blob["sha"]}
                )
            )
        return artifacts

    async def _ingest_pull_requests(self, client: httpx.AsyncClient) -> list[NormalizedArtifact]:
        resp = await client.get(
            f"/repos/{self.owner}/{self.repo}/pulls", params={"state": "all", "per_page": 100}
        )
        resp.raise_for_status()
        return [self.normalize_artifact({"type": "pull_request", **pr}) for pr in resp.json()]

    async def _ingest_commits(self, client: httpx.AsyncClient) -> list[NormalizedArtifact]:
        resp = await client.get(
            f"/repos/{self.owner}/{self.repo}/commits", params={"per_page": 100}
        )
        resp.raise_for_status()
        return [self.normalize_artifact({"type": "commit", **c}) for c in resp.json()]

    async def _ingest_issues(self, client: httpx.AsyncClient) -> list[NormalizedArtifact]:
        resp = await client.get(
            f"/repos/{self.owner}/{self.repo}/issues", params={"state": "all", "per_page": 100}
        )
        resp.raise_for_status()
        # GitHub's /issues endpoint also returns PRs — exclude those, they're
        # already covered by _ingest_pull_requests.
        return [
            self.normalize_artifact({"type": "issue", **issue})
            for issue in resp.json()
            if "pull_request" not in issue
        ]

    def normalize_artifact(self, raw: dict[str, Any]) -> NormalizedArtifact:
        kind = raw["type"]
        if kind == "file":
            return NormalizedArtifact(
                source_artifact_id=raw["sha"],
                artifact_type="source_file",
                title=raw["path"],
                content=raw["content"],
                source_url=f"https://github.com/{self.owner}/{self.repo}/blob/HEAD/{raw['path']}",
                checksum=raw["sha"],
            )
        if kind == "pull_request":
            return NormalizedArtifact(
                source_artifact_id=str(raw["number"]),
                artifact_type="pull_request",
                title=raw["title"],
                content=raw.get("body") or "",
                source_url=raw["html_url"],
                author=raw["user"]["login"] if raw.get("user") else None,
                created_at=_parse_dt(raw.get("created_at")),
                updated_at=_parse_dt(raw.get("updated_at")),
                structured_content={
                    "state": raw["state"],
                    "merged": raw.get("merged_at") is not None,
                },
            )
        if kind == "commit":
            return NormalizedArtifact(
                source_artifact_id=raw["sha"],
                artifact_type="commit",
                title=raw["commit"]["message"].splitlines()[0],
                content=raw["commit"]["message"],
                source_url=raw["html_url"],
                author=raw["commit"]["author"]["name"] if raw["commit"].get("author") else None,
                created_at=_parse_dt(
                    raw["commit"]["author"]["date"] if raw["commit"].get("author") else None
                ),
                checksum=raw["sha"],
            )
        if kind == "issue":
            return NormalizedArtifact(
                source_artifact_id=str(raw["number"]),
                artifact_type="issue",
                title=raw["title"],
                content=raw.get("body") or "",
                source_url=raw["html_url"],
                author=raw["user"]["login"] if raw.get("user") else None,
                created_at=_parse_dt(raw.get("created_at")),
                updated_at=_parse_dt(raw.get("updated_at")),
                structured_content={"state": raw["state"]},
            )
        raise ValueError(f"Unknown GitHub artifact kind: {kind}")

    async def normalize_relationship(
        self, artifacts: list[NormalizedArtifact]
    ) -> list[tuple[str, str, str]]:
        # Deterministic same-connector relationships GitHub's own metadata
        # gives us directly, distinct from relationship_svc's cross-connector
        # (Notion<->GitHub) link extraction (research.md §4). Left empty for
        # Phase 1: PR<->commit linkage would need the PR commits endpoint,
        # which is a reasonable Phase 2 addition, not required by spec.md's
        # acceptance criteria for this workflow.
        return []


def _parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00"))
