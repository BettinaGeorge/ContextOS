from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any


@dataclass
class NormalizedArtifact:
    """The common shape every connector's normalize_artifact() must produce,
    before it's persisted as a models.artifact.Artifact row. Matches the
    canonical artifact model (docs/prd.md §6 / data-model.md)."""

    source_artifact_id: str
    artifact_type: str
    title: str
    content: str
    source_url: str
    structured_content: dict[str, Any] | None = None
    author: str | None = None
    created_at: Any = None
    updated_at: Any = None
    checksum: str | None = None


@dataclass
class ConnectorHealth:
    healthy: bool
    detail: str | None = None


class ConnectorAuthError(Exception):
    """Raised specifically when authenticate() fails because the credential
    itself is invalid/expired/revoked (e.g. GitHub 401/403, Notion
    "unauthorized"). ingestion_svc (T055) maps this to
    ConnectorStatus.needs_reconnect instead of the generic `failed`, since
    the user's actual next step differs: reconnect with a new token, not
    just retry."""


class BaseConnector(ABC):
    """Common interface every connector implements (handoff §11), so core
    retrieval/reasoning code never depends on GitHub- or Notion-specific
    logic directly."""

    @abstractmethod
    async def authenticate(self) -> None:
        """Validate the stored credential actually works. Raise on failure."""

    @abstractmethod
    async def ingest_full(self) -> list[NormalizedArtifact]:
        """Fetch and normalize everything in scope for this connector. Full
        (non-incremental) re-ingestion only, per PRD §4 Phase 1 scope."""

    @abstractmethod
    def normalize_artifact(self, raw: Any) -> NormalizedArtifact:
        """Map one raw item from the source system into NormalizedArtifact."""

    @abstractmethod
    async def normalize_relationship(
        self, artifacts: list[NormalizedArtifact]
    ) -> list[tuple[str, str, str]]:
        """Return (source_artifact_id, target_artifact_id, relationship_type)
        triples derivable directly from this connector's own data (e.g. a
        commit belonging to a PR) — not the cross-connector deterministic
        linking that relationship_svc handles separately (research.md §4)."""

    @abstractmethod
    async def health_check(self) -> ConnectorHealth:
        """Cheap check used by GET /connectors/{id}/status — must not do a
        full re-ingestion."""
