# Phase 0 Research: Phase 1 Reliability Hardening

Each decision below is made against the code as it exists on `main` (commit `eeaa447`). Items that need a real database to confirm are listed in section 14 and checked in `quickstart.md`, not assumed.

## 1. What is an artifact's identity? (FR-005, FR-006)

**Decision**: The identity key is `(workspace_id, source_system, artifact_type, source_artifact_id)`. For GitHub source files, `source_artifact_id` changes from the blob SHA to the **file path**. Pieces of a chunked file are `"{path}#chunk{n}"` as today.

**Rationale**: Today a file's `source_artifact_id` is its blob SHA, so editing a file produces a new identity. The old version is never updated or removed and stays searchable. Two files with identical content at different paths also share one SHA, so a uniqueness rule on the SHA would reject the second file. Commits (SHA), issues and pull requests (number) and Notion pages (page ID) are already stable. `artifact_type` joins the key because a file named `5` and issue `#5` would otherwise collide.

**Alternatives considered**: Keep SHA identity and add a path column to the key (rejected: an edited file would still be a new artifact). Key on `source_url` (rejected: chunk URLs embed line ranges that shift when code moves).

## 2. How is "unchanged" detected? (FR-007, FR-008)

**Decision**: `ConnectorService` computes SHA-256 of each stored piece's `content` and writes it to `checksum`. Connector-supplied SHAs are no longer used for change detection.

**Rationale**: Only source files and commits supply a checksum today. Pull requests, issues and Notion pages supply `None`, so a checksum-based rule would never skip them. A hash computed in one place also covers chunk pieces, and it stays correct if the chunker changes (roadmap Phase 2 plans to improve chunking).

**Alternatives considered**: Per-connector checksums (rejected: three of five types have none). Compare content text directly (rejected: needs every row's full content loaded to compare).

## 3. How does re-ingestion write? (FR-007 to FR-009, FR-011)

**Decision**: Before embedding, load the existing `(identity, checksum, title, source_url, has_embedding)` for the workspace and source system and split the new rows into: new, content-changed, metadata-only changed, and unchanged. Embed only new and content-changed rows. Write with `INSERT ... ON CONFLICT (identity) DO UPDATE` so IDs stay stable. Unchanged rows are not written. After writing, for each source file seen, delete pieces of that file that are not in the current set (covers a file that shrinks, or flips between one piece and several).

**Rationale**: Stable IDs keep relationships and citations valid, because both relationship foreign keys cascade on delete. A row whose content is unchanged but whose title or line-range URL moved is updated without a new embedding, so citations keep pointing at the right lines. Because the write is a single upsert per identity, a failed run followed by a re-run converges, and two overlapping runs cannot create duplicates (see section 10).

**Alternatives considered**: Delete-then-reinsert per connector (rejected: cascades away relationships and re-embeds everything). Soft delete via the unused `deleted_at` column (rejected: out of scope, and not needed when nothing is removed except stale pieces).

## 4. Relationship uniqueness (FR-010)

**Decision**: Unique constraint on `(workspace_id, source_artifact_id, target_artifact_id, relationship_type)`. `RelationshipRepository.create` becomes `INSERT ... ON CONFLICT DO NOTHING` followed by a select, so it still returns the row. `relationship_svc` counts only newly created rows.

**Rationale**: Its own comment says Phase 1 "accepts possible duplicate rows." Extraction runs after every ingest, so duplicates grow with each run. Keeping `create`'s signature avoids changing existing tests.

## 5. Rollout migration for existing data (spec Edge Cases, Assumptions)

**Decision**: One Alembic migration, in this order inside one transaction:

1. Delete all existing `github` `source_file` artifacts (identity scheme changed; they are rebuilt by the next ingest; relationships never reference files).
2. Collapse duplicate artifacts per identity, keeping the newest `ingested_at` (ties: highest `id`). Before deleting a loser, repoint relationships and `parent_id` references to the keeper.
3. Collapse duplicate relationships per `(workspace, source, target, type)`.
4. For connectors with more than one active job, mark all but the newest as `failed` ("superseded by migration").
5. Add the unique constraints, the partial unique index on jobs, and the search column and index.

The migration is run first against a copy of the real database and its before/after counts are reviewed (quickstart scenario 7). Connectors must be re-ingested after upgrade so that code files return.

**Rationale**: Re-keying legacy file rows from SHA to path would need path recovery from `source_url`, and would leave leftover high-numbered pieces from older versions. The data is derived and reproducible, so deleting is simpler and less error-prone than a clever migration. The cost is one full re-embed of code files, which every ingest does today anyway.

**Alternatives considered**: Re-key in SQL by parsing paths out of `source_url` (rejected: fragile, leaves stale pieces). Skip cleanup and add constraints `NOT VALID` (rejected: duplicates would stay and keep skewing retrieval).

## 6. Keyword search (FR-012, FR-013, FR-015, FR-016)

**Decision**: Add a stored generated column `search_vector` on `artifacts`, defined as `to_tsvector('english', title || ' ' || left(content, 200000))`, with a GIN index. The question is tokenised in Python with `[A-Za-z0-9]+`, lower-cased, length at least 2, de-duplicated and capped at 12 tokens. The tokens are joined with ` | ` and passed to `to_tsquery('english', ...)`. Results are filtered by `workspace_id`, ordered by `ts_rank`, and limited. If no tokens remain, the keyword path returns an empty list without querying.

**Rationale**: `websearch_to_tsquery` and `plainto_tsquery` AND all terms, so a normal question fails whenever one word is missing from the artifact. OR with ranking returns partial matches ordered by how many terms hit. Restricting tokens to letters and digits means no operator or quote can reach the query parser, which satisfies the special-character requirement without escaping. The 200,000-character cap keeps a single huge page from exceeding PostgreSQL's tsvector size limit and failing ingestion. Requires PostgreSQL 12 or later for generated columns.

**Alternatives considered**: `pg_trgm` similarity (rejected: needs an extension and ranks poorly on long text). BM25 extensions or an external search service (rejected: new dependency, violates the $0 and no-new-service constraints). `websearch_to_tsquery` (rejected: AND semantics).

## 7. Merging keyword and vector results (FR-014)

**Decision**: Reciprocal rank fusion in Python inside `RetrievalService`. Each list contributes `1 / (60 + rank)` per artifact; scores are summed by artifact ID; results are sorted by score and cut to the limit. Both lists are limited to the same size before fusion.

**Rationale**: It needs no score normalisation (keyword rank and cosine distance are not comparable), is a pure function that is easy to unit test, and gives the required behavior: ranked well by both beats ranked well by one. The constant 60 is the commonly used default and is a named constant that can be tuned later.

**Alternatives considered**: Weighted score mixing (rejected: scales are incompatible). Fusing in SQL (rejected: more complex, harder to test).

## 8. Retry state (FR-017 to FR-021)

**Decision**: Retry is represented as `status = queued` plus a new nullable `next_attempt_at`. No new enum value on jobs or connectors. Constants: `BACKOFF_SECONDS = (30, 120)`, so `MAX_ATTEMPTS = 3`. The existing `attempts` counter (incremented when a job is claimed) is the attempt number. Permanent failures are `ConnectorAuthError` and `ValueError` (missing connector); everything else is retried.

**Rationale**: Adding a value to a PostgreSQL enum needs `ALTER TYPE` handling in Alembic, and the connector status enum would also change, which would collide with feature 002's connector migration. Deriving "waiting to retry" as `queued AND attempts > 0` avoids both. While retries remain, the connector stays `ingesting`; the connector turns `failed` only on the final attempt. This resolves the spec's conditional note about a possible "retrying" state: none is needed.

**Alternatives considered**: New `retrying` enum value (rejected: migration cost and conflict with feature 002). Retrying inside the handler with `asyncio.sleep` (rejected: holds the worker idle and loses the retry on restart).

## 9. Safe job claiming (FR-023, FR-024)

**Decision**: `claim_oldest_queued` becomes a single query `SELECT ... WHERE status = 'queued' AND (next_attempt_at IS NULL OR next_attempt_at <= now()) ORDER BY created_at LIMIT 1 FOR UPDATE SKIP LOCKED`, followed by the status update in the same transaction.

**Rationale**: `SKIP LOCKED` makes concurrent workers skip rows another worker holds, so a second worker takes the next job instead of waiting or double-claiming. This is the same effect as consumer-group partition assignment: each unit of work goes to one consumer.

## 10. One active job per connector, and stuck jobs (FR-022, spec Edge Cases)

**Decision**: Partial unique index on `jobs (connector_id) WHERE status IN ('queued', 'running')`. `enqueue` first marks any `running` job older than 60 minutes as `failed` ("abandoned: worker stopped"), then inserts. If the insert conflicts, it returns the existing active job and the endpoint responds as before with that job.

**Rationale**: The index makes a second concurrent trigger a no-op. It also introduces a new failure: a job stuck in `running` after a crash would block that connector forever, which is worse than today. The age-based sweep prevents that regression without building a general recovery system. If a long but healthy job is wrongly swept and a second run starts, idempotent ingestion (section 3) makes the overlap harmless. 60 minutes is a named constant, chosen because rate-limited embedding of a large repository can legitimately take many minutes.

**Alternatives considered**: No index, check in application code (rejected: racy). Reset all `running` jobs at process start (rejected: unsafe once more than one instance runs). A full lease and heartbeat system (rejected: out of scope).

## 11. Status visibility (FR-019 to FR-021)

**Decision**: Add `attempts`, `max_attempts` and `next_attempt_at` to the job status response. Add `ingestion_attempts`, `max_attempts` and `next_attempt_at` (nullable) to the connector status responses, taken from the connector's most recent job. The status page shows "Retrying (attempt 2 of 3)" while the connector is `ingesting` with `attempts > 0`, and renders the latest error in a muted style until the connector is `failed`. All changes are additive.

**Rationale**: The status page reads connector status, not job status, so the attempt data must be on the connector response. Additive fields keep older clients working.

## 12. Escaping retrieved content (FR-001 to FR-003)

**Decision**: Apply `html.escape(value, quote=True)` to every field interpolated into the evidence block (identifier, type, origin, source address) and `html.escape(value, quote=False)` to content. Add one sentence to the fixed system prompt: evidence is escaped, `&lt;` means a literal `<`, and quoted evidence should be written with the original characters. The tests add the adversarial set from FR-003.

**Rationale**: Escaping makes a forged tag textually impossible, which is the strongest reading of "cannot begin an additional item." Verified on a replica of the current formatting code: one real item produced two evidence sections, and text after the first closing tag sat outside the data block.

**Alternatives considered**: A per-request random boundary token (rejected: forged `<item>` lookalikes would still appear inside content and rely on the model ignoring them). Escaping only the delimiter strings (rejected: a denylist is easy to bypass with case, spacing or partial tags). The cost of escaping is that code containing `<` or `&` is shown to the model in escaped form; the prompt sentence mitigates this.

## 13. Baseline for keyword search (SC-006)

**Decision**: The first piece of work records the baseline: a question set with the expected artifact for each, and the current keyword result for every question, saved to `specs/003-reliability-hardening/baseline.md` before any retrieval change.

**Dependency on the owner**: `docs/prd.md` §7 and feature 001's quickstart both call for about ten hand-written questions, but no such list exists in the repository (feature 001 task T061 was never run). The owner must write them, each paired with the URL of the artifact that should be found.

## 14. To confirm against a real database (quickstart, not assumed)

- How the `english` configuration tokenizes code identifiers such as `get_by_id` (checked with `ts_debug`).
- That a query made only of stop words (for example `the | how`) returns no rows and no error.
- That the generated column, GIN index and `ts_rank` ordering behave as designed on a copy of real data.
- That the PostgreSQL version on the hosted Supabase project is 12 or later.
- That existing tests which reuse `source_artifact_id="1"` for more than one artifact in the same workspace and type still pass; if not, only fixture IDs change, not assertions.
- Two existing tests (`test_handle_ingestion_job_marks_connector_failed_on_error` in `test_ingestion_svc.py` and `test_generic_failure_sets_failed_not_needs_reconnect` in `test_ingestion_failure.py`) fail a freshly enqueued job (zero attempts) with a generic error and assert the connector is `failed`. That is the old fail-on-first-error behavior, which FR-019 deliberately replaces. Their assertions stay as written; their job fixtures are set to the final attempt. This is the only existing test whose setup has to change for behavioral rather than identity reasons.
