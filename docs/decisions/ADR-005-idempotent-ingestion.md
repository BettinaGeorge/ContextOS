# ADR-005: Idempotent ingestion by stable identity and content hash

Status: Proposed (accepted when `specs/003-reliability-hardening/spec.md` is approved).

## Context

Every ingestion inserts a fresh row for every artifact and re-embeds all of them. The database has no uniqueness rule on artifacts or relationships. GitHub source files use the blob SHA as their `source_artifact_id`, so an edited file becomes a new artifact and the old version stays searchable, and two files with identical content share one ID. Only source files and commits carry a checksum; pull requests, issues and Notion pages have none.

## Decision

- Identity is `(workspace_id, source_system, artifact_type, source_artifact_id)`, enforced by a unique constraint. GitHub source files are identified by path (`{path}`, `{path}#chunk{n}`).
- `ConnectorService` computes SHA-256 of each piece's content and stores it in `checksum`. Only new or content-changed pieces are embedded.
- Writes are `INSERT ... ON CONFLICT DO UPDATE`, so artifact IDs stay stable and relationships (which cascade on delete) survive.
- Stale pieces of a re-ingested file are deleted after the write.
- Relationships get a unique constraint and insert-or-ignore.
- A one-time migration deletes legacy GitHub source files, collapses duplicates (repointing relationships first), and then adds the constraints.

## Consequences

- A re-ingest with no change makes zero embedding requests and no writes for unchanged pieces.
- The first ingest after upgrade re-embeds code files once, because legacy file rows are removed.
- The migration deletes rows and must be rehearsed on a copy of real data.
- Items deleted at the source still remain (no incremental sync); out of scope.

## Alternatives considered

- **Keep SHA identity, add path to the key**: an edited file would still be a new artifact.
- **Delete and reinsert per connector**: cascades away relationships and re-embeds everything.
- **Per-connector checksums**: three of five artifact types supply none.
- **Re-key legacy rows in SQL by parsing `source_url`**: fragile and leaves stale pieces from older versions.
