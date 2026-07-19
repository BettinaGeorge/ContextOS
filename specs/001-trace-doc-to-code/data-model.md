# Phase 1 Data Model: Trace a Spec/Doc to Code

All tables carry `workspace_id` per Constitution Principle VI, even though only one workspace is exercised in this phase. This extends the canonical model in `docs/prd.md` §6 with the fields needed to actually implement it.

## Workspace

The isolation boundary for a user's connected tools and ingested data.

| Field | Type | Notes |
|---|---|---|
| id | uuid, PK | |
| owner_user_id | text | Supabase Auth user id (`sub` claim) |
| name | text | |
| created_at | timestamptz | |

**Validation rule**: a workspace owns at most one `connector` per `source_system` in this phase (unique constraint on `(workspace_id, source_system)`) — enforces the "single repo, single Notion source" scope from spec.md.

## Connector

A connection to an external system (GitHub or Notion), scoped to one workspace.

| Field | Type | Notes |
|---|---|---|
| id | uuid, PK | |
| workspace_id | uuid, FK → workspace | |
| source_system | enum(`github`, `notion`) | |
| status | enum(`connected`, `ingesting`, `complete`, `failed`, `needs_reconnect`) | |
| encrypted_access_token | text | encrypted at rest per Constitution Principle III / FR-016 |
| external_resource_ref | text | repo `owner/name` for GitHub; selected page/database ids for Notion |
| last_ingested_at | timestamptz, nullable | |
| error_message | text, nullable | populated when status = `failed` |
| created_at / updated_at | timestamptz | |

**State transitions**: `connected` → `ingesting` → (`complete` | `failed`). `failed` → `ingesting` on manual retry, or → `needs_reconnect` if the failure was an auth error specifically.

## Artifact

A normalized representation of one ingested item. Matches `docs/prd.md` §6's canonical model.

| Field | Type | Notes |
|---|---|---|
| id | uuid, PK | |
| workspace_id | uuid, FK → workspace | |
| source_system | enum(`github`, `notion`) | |
| source_artifact_id | text | the id/URL in the origin system |
| artifact_type | enum(`source_file`, `commit`, `pull_request`, `issue`, `document`) | Phase 1 subset of the full canonical type list |
| title | text | |
| content | text | raw or lightly-cleaned text |
| structured_content | jsonb, nullable | e.g. Notion block structure, diff stats |
| author | text, nullable | |
| created_at / updated_at | timestamptz | from the source system, not ingestion time |
| source_url | text | always populated — every citation needs an openable link (FR-010) |
| parent_id | uuid, nullable, FK → artifact | e.g. a chunk's parent file/page |
| checksum | text | for detecting unchanged content on re-ingestion |
| ingestion_version | int | |
| deleted_at | timestamptz, nullable | |
| embedding | vector | via Voyage `voyage-code-3`; nullable until embedding completes |

**Validation rule**: `source_url` is required (not nullable) — a citation with no link violates FR-010/SC-004.

## Relationship

A directed link between two artifacts.

| Field | Type | Notes |
|---|---|---|
| id | uuid, PK | |
| workspace_id | uuid, FK → workspace | |
| source_artifact_id | uuid, FK → artifact | |
| target_artifact_id | uuid, FK → artifact | |
| relationship_type | text | e.g. `references`, `implements` |
| relationship_origin | enum(`explicit`, `metadata-derived`, `model-inferred`, `user-confirmed`) | Phase 1 code paths only ever write `explicit` or `metadata-derived` (research.md §4) — the other two values exist in the schema for forward compatibility (Constitution allows this; PRD §6 confirms) but are not produced by any Phase 1 logic |
| confidence | float, nullable | populated only when `relationship_origin = model-inferred` (not used in Phase 1) |
| evidence | text, nullable | e.g. the exact URL substring matched, for auditability |
| created_at / updated_at | timestamptz | |

**Validation rule**: application code enforces `relationship_origin IN ('explicit', 'metadata-derived')` for any row written in Phase 1 — a check constraint mirrors this at the DB level so a future bug can't silently write an unlabeled inferred relationship (Constitution Principle II).

## Job

Backs the Postgres-based ingestion queue from ADR-001 (not a full canonical-model entity — internal to ingestion, not user-facing content).

| Field | Type | Notes |
|---|---|---|
| id | uuid, PK | |
| workspace_id | uuid, FK → workspace | |
| connector_id | uuid, FK → connector | |
| job_type | enum(`ingest_github`, `ingest_notion`) | |
| status | enum(`queued`, `running`, `complete`, `failed`) | |
| attempts | int, default 0 | |
| error_message | text, nullable | |
| created_at / started_at / completed_at | timestamptz, nullable | |

**State transitions**: `queued` → `running` → (`complete` | `failed`). The in-process poller (research.md §1) picks the oldest `queued` row, sets `running`, and updates on completion/failure.
