# Phase 1 Data Model: Phase 1 Reliability Hardening

Only changes are listed. Everything not mentioned is unchanged from `specs/001-trace-doc-to-code/data-model.md`.

## Artifact (changed)

| Field | Change | Notes |
|---|---|---|
| (workspace_id, source_system, artifact_type, source_artifact_id) | **NEW unique constraint** `uq_artifact_identity` | Identity of one stored piece. |
| source_artifact_id | **meaning changed for GitHub source files** | Now the file path (`{path}`, or `{path}#chunk{n}` for pieces). Was the blob SHA. Other types unchanged. |
| checksum | **meaning changed** | SHA-256 of `content`, computed by `ConnectorService` for every piece. Connector-supplied SHAs are no longer stored here. |
| ingestion_version | **now used** | Incremented each time content changes in place. Starts at 1. |
| search_vector | **NEW**, tsvector, stored generated column, deferred load | `to_tsvector('english', title || ' ' || left(content, 200000))`. Never written by application code. |
| ix_artifacts_search_vector | **NEW** GIN index on `search_vector` | |

**Validation rules**

- A piece whose `checksum` equals the stored one is not re-embedded and not rewritten.
- A piece whose `checksum` is unchanged but whose `title` or `source_url` differs is updated without touching `embedding`.
- After ingesting a source file, no piece of that file exists whose `source_artifact_id` is not in the current set for that file.

## Relationship (changed)

| Field | Change | Notes |
|---|---|---|
| (workspace_id, source_artifact_id, target_artifact_id, relationship_type) | **NEW unique constraint** `uq_relationship_edge` | Inserts use `ON CONFLICT DO NOTHING`. |

Relationship rows keep referencing artifact IDs. Because ingestion now updates artifacts in place, those IDs stay valid across re-ingestion.

## Job (changed)

| Field | Change | Notes |
|---|---|---|
| next_attempt_at | **NEW**, timestamptz, nullable | Earliest time a queued job may be claimed. Null means "now". |
| uq_jobs_one_active_per_connector | **NEW** partial unique index on `(connector_id)` where `status IN ('queued','running')` | At most one active job per connector. |

No new enum values. The existing `attempts` column is incremented when a job is claimed and is the attempt number.

**State derivation**

| status | attempts | next_attempt_at | Meaning shown to the operator |
|---|---|---|---|
| queued | 0 | null | Waiting for first run |
| queued | > 0 | in the future | Waiting to retry (still in progress) |
| running | ≥ 1 | any | Running attempt N |
| complete | ≥ 1 | any | Done |
| failed | ≥ 1 | any | Failed after the final attempt, or failed permanently; `error_message` holds the last error |

**State transitions**

- claim: `queued` and due → `running`, `attempts += 1`
- success: `running` → `complete`
- transient failure with `attempts < MAX_ATTEMPTS`: `running` → `queued`, `next_attempt_at = now + BACKOFF_SECONDS[attempts - 1]`, `error_message` = latest error
- transient failure with `attempts >= MAX_ATTEMPTS`: `running` → `failed`
- permanent failure (credential rejected, connector missing): `running` → `failed` on the first attempt
- abandoned: `running` for more than 60 minutes, detected at enqueue → `failed` ("abandoned: worker stopped")

## Connector (no schema change)

`status` enum is unchanged. While a job has retries remaining the connector stays `ingesting`. It becomes `failed` only on the final failed attempt, and `needs_reconnect` on a credential rejection, as today.

## Constants (code, not columns)

| Name | Value | Where |
|---|---|---|
| BACKOFF_SECONDS | (30, 120) | job worker |
| MAX_ATTEMPTS | 3 (length of BACKOFF_SECONDS plus 1) | job worker |
| STALE_RUNNING_AFTER | 60 minutes | job repository |
| RRF_K | 60 | retrieval service |
| SEARCH_CONTENT_CHAR_LIMIT | 200000 | migration (generated column) |
| MAX_QUERY_TOKENS | 12 | artifact repository |

## Migration order

One Alembic revision whose `down_revision` is `4500f22c8686`. Steps run in one transaction, in this order, per `research.md` §5: purge legacy GitHub source files, collapse duplicate artifacts (repointing relationships and `parent_id`), collapse duplicate relationships, supersede surplus active jobs, then add constraints, the partial index, `next_attempt_at`, and the search column and index.

**Interaction with feature 002 (parked)**: this revision touches artifacts, relationships and jobs only, and adds no connector enum value. Feature 002's planned connector migration (task T006) is independent. If 002 is built later, its revision must set `down_revision` to this one.
