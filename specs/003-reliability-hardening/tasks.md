---

description: "Task list for Phase 1 Reliability Hardening"
---

# Tasks: Phase 1 Reliability Hardening

**Input**: Design documents from `/specs/003-reliability-hardening/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/api.md, quickstart.md (all present). ADR-005 to ADR-008 written, status Proposed until the spec is approved.

**Tests**: Included for every story and written before the implementation they cover. They must fail first, then pass (constitution: `code → tests → validation`).

**Organization**: One phase per user story in spec priority order (US1 escaping P1, US2 idempotent ingestion P1, US3 search P2, US4 retry P2, US5 claiming P3). The plan's work order is preserved: baseline, escaping, ingestion and migration, search, jobs, docs.

**Owner-blocked tasks** are marked `(OWNER)`. They need the owner's own data or a decision and cannot be finished by an agent working alone: T001, T003, T013, T034, T058.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: can run in parallel (different files, no dependency on an unfinished task)
- **[Story]**: US1 to US5, mapping to spec.md
- Paths follow plan.md (`backend/`, `frontend/`, `docs/`, `specs/`)

## Notes that apply to the whole list

- No new dependencies (FR-025). Use only the standard library and the SQLAlchemy PostgreSQL dialect already installed.
- Existing test **assertions are never edited** (FR-026). Allowed edits to existing tests are limited to fixture data: artifact identity values (T012) and a job's attempt count (T042). Everything else is new test files or new test functions.
- Every new query filters by `workspace_id` (Constitution Principle VI). The job claim stays cross-workspace by design, as today.
- Tests that downgrade and upgrade the schema (T006) run only against a scratch database whose name ends in `_dev` or `_test`, and skip otherwise.

---

## Phase 1: Setup

**Purpose**: Record the baseline and confirm the environment before any change.

- [ ] T001 (OWNER) Write about ten real questions about your own repo and Notion pages in `specs/003-reliability-hardening/baseline.md`, each paired with the URL of the artifact that should be found. This is the question set that `docs/prd.md` §7 calls for and that does not yet exist.
- [ ] T002 [P] Create `backend/scripts/keyword_baseline.py`: reads the questions from `baseline.md`, runs each through `ArtifactRepository.search_fulltext` for the owner's workspace, and prints whether the expected URL is in the first ten results. It must work unchanged before and after US3 so the two runs are comparable.
- [ ] T003 (OWNER) Run `backend/scripts/keyword_baseline.py` against your populated local database **on the unmodified retrieval code** (commit `eeaa447` or later without US3 changes) and record the commit hash and per-question results in `specs/003-reliability-hardening/baseline.md`. No retrieval change (T031, T032) may start before this is committed.
- [ ] T004 [P] Confirm PostgreSQL is 12 or later locally (`SHOW server_version`) and on the hosted Supabase project. Record both in `specs/003-reliability-hardening/plan.md` under Technical Context if either differs from what is written there.
- [ ] T005 [P] Run the full existing suites on the starting commit (`uv run pytest` in `backend/`, `pnpm test` in `frontend/`) and record pass/fail counts in `specs/003-reliability-hardening/baseline.md`, so later failures can be attributed to this feature.

---

## Phase 2: Foundational (blocks US2 to US5; US1 does not depend on it)

**Purpose**: The one schema migration that US2 to US5 build on, written test-first and rehearsed before it touches real data.

**⚠️ CRITICAL**: US2, US3, US4 and US5 cannot start until T011 passes. US1 may proceed in parallel with this whole phase.

- [ ] T006 Write the migration test first in `backend/tests/integration/test_reliability_migration.py`. It skips unless the connected database name ends in `_dev` or `_test`. It downgrades to revision `4500f22c8686`, seeds: two artifacts with the same identity (different `ingested_at`), a relationship pointing at each, duplicate relationships for one pair and type, a legacy GitHub `source_file` row keyed by blob SHA, and two active jobs for one connector. It upgrades to head and asserts: one artifact per identity (the newest), the surviving artifact holds the repointed relationships exactly once per pair and type, the legacy source-file row is gone, one active job per connector, and the new constraints, partial index, `next_attempt_at`, `search_vector` and GIN index exist. Run it and confirm it fails.
- [ ] T007 [P] Update `backend/src/models/artifact.py`: add unique constraint `uq_artifact_identity` on `(workspace_id, source_system, artifact_type, source_artifact_id)`, and a deferred `search_vector` tsvector column declared as a stored generated column using the expression in `data-model.md`.
- [ ] T008 [P] Update `backend/src/models/relationship.py`: add unique constraint `uq_relationship_edge` on `(workspace_id, source_artifact_id, target_artifact_id, relationship_type)`.
- [ ] T009 [P] Update `backend/src/models/job.py`: add nullable `next_attempt_at` (timestamptz) and the partial unique index `uq_jobs_one_active_per_connector` on `(connector_id)` where `status IN ('queued','running')`.
- [ ] T010 Create the Alembic revision in `backend/alembic/versions/` with `down_revision = "4500f22c8686"`, running in one transaction in the order in `data-model.md` ("Migration order"): purge legacy GitHub source files, collapse duplicate artifacts (repoint relationships and `parent_id` to the keeper first; keeper is newest `ingested_at`, ties highest `id`), collapse duplicate relationships, supersede surplus active jobs as `failed` ("superseded by migration"), then add the constraints, partial index, `next_attempt_at`, `search_vector` and GIN index. `downgrade()` drops the added objects and states in a comment that deleted rows are not restored.
- [ ] T011 Make T006 pass. Then on an empty scratch database run `uv run alembic upgrade head`, `uv run alembic downgrade -1`, `uv run alembic upgrade head` and confirm the round trip is clean.
- [ ] T012 Fix existing test fixtures that now collide with `uq_artifact_identity`. Run `uv run pytest` and, for each `IntegrityError` on that constraint, change **only the artifact identity values** in the fixture (candidates: `backend/tests/unit/test_retrieval_svc.py`, `test_answer_svc.py`, `test_relationship_svc.py`, `test_workspace_isolation.py`, `backend/tests/integration/test_trace_doc_no_link.py`, `test_trace_doc_flow.py`). Do not touch any assertion. List each changed file in the commit message.
- [ ] T013 (OWNER) Rehearse the migration on a copy of real data, following `quickstart.md` scenario 7 (`createdb -p 5433 -T contextos_dev contextos_dev_copy`, or `pg_dump` for a hosted database). Record the before and after counts and the post-re-ingest relationship check in `specs/003-reliability-hardening/migration-rehearsal.md`, and review them. **This blocks applying the migration to any database that is not a scratch database.** It does not block coding US2 to US5 on scratch databases.

**Checkpoint**: Schema ready on scratch databases. US2 to US5 may begin.

---

## Phase 3: User Story 1 - Untrusted content cannot rewrite the prompt structure (Priority: P1) 🎯 MVP

**Goal**: Retrieved content and item attributes cannot end the evidence section, add items, or change another field.

**Independent Test**: Render evidence built from break-out strings and assert one evidence section, the same number of items as input, and unchanged attribute values. Needs no database.

### Tests for User Story 1 (write first, confirm they fail)

- [x] T014 [P] [US1] Add `backend/tests/unit/test_evidence_escaping.py` with the adversarial set from FR-003, at least eight patterns: closing evidence tag in content; fake complete `<item>` in content; quote and extra attribute in `source_url`; the same in `artifact_type`, `origin` and `artifact_id`; nested or malformed tags; upper-case and spaced variants (`</EVIDENCE >`); an entity-like string (`&lt;/evidence&gt;`) to confirm it is escaped once, not decoded; and text imitating `[cite:ID]`. Each asserts exactly one `<evidence>` and one `</evidence>`, item count equals input count, and attribute values round-trip through `html.unescape`.
- [ ] T015 [P] [US1] Add `backend/tests/unit/test_cite_marker_in_evidence.py`: evidence content containing `[cite:<id of an artifact that was not retrieved>]` and a model reply that echoes it produces no citation for that id (confirms FR-004 is untouched). Use the existing fake-client pattern from `test_answer_svc.py` without editing that file.

### Implementation for User Story 1

- [x] T016 [US1] In `backend/src/llm/groq_client.py`, escape every attribute value with `html.escape(value, quote=True)` and every item body with `html.escape(value, quote=False)` inside `_build_evidence_block`. Add one sentence to `SYSTEM_PROMPT` stating that evidence is escaped, that `&lt;` means a literal `<`, and that quoted evidence should use the original characters.
- [ ] T017 [US1] Run T014 and T015 (now passing) and the existing `backend/tests/unit/test_prompt_isolation.py` and `test_answer_svc.py` unchanged. Run `quickstart.md` scenario 1.

**Checkpoint**: US1 is shippable on its own (ADR-008).

---

## Phase 4: User Story 2 - Re-ingesting never duplicates or needlessly re-embeds (Priority: P1)

**Goal**: Same artifacts and relationships after any number of ingestions; only new or changed content is embedded; edited files update in place.

**Independent Test**: Ingest a fixture source twice, then edit one item and ingest again; compare counts, embedding calls and stored content.

**Depends on**: Phase 2 (T011, T012).

### Tests for User Story 2 (write first, confirm they fail)

- [ ] T018 [P] [US2] Add `backend/tests/unit/test_ingestion_partition.py` for the pure function that splits new rows against existing stored state into new, content-changed, metadata-only-changed and unchanged. Cover: same content and same metadata is unchanged; same content but different title or `source_url` is metadata-only; different content is content-changed; missing embedding forces re-embed; identical content at two different paths stays two rows.
- [ ] T019 [P] [US2] Add `backend/tests/integration/test_idempotent_ingestion.py`: ingest a fixture source twice with a counting fake embedding client and assert identical artifact and relationship counts and zero embedding calls on the second run (SC-001).
- [ ] T020 [P] [US2] Add `backend/tests/integration/test_ingestion_changes.py`: (a) changing one file re-embeds only that file's pieces, increments `ingestion_version`, and leaves no old version searchable (SC-002); (b) a file that shrinks from several pieces to fewer leaves no leftover pieces, and one that flips between one piece and several leaves no stale row; (c) a run that fails after some rows are written, then re-runs, ends identical to one clean run; (d) re-ingesting workspace A leaves workspace B's artifacts untouched; (e) two different files with identical content remain two artifacts.
- [ ] T021 [P] [US2] Add `backend/tests/integration/test_relationship_idempotent.py`: run `RelationshipService.extract_for_workspace` twice and assert each edge exists once and the returned count on the second run is zero.
- [ ] T022 [P] [US2] Add a new test function (do not edit existing ones) to `backend/tests/unit/test_github_connector.py` asserting a source file's `source_artifact_id` is its path and that two files with the same blob SHA at different paths get different ids.

### Implementation for User Story 2

- [ ] T023 [US2] In `backend/src/connectors/github_connector.py`, set `source_artifact_id=raw["path"]` for source files. Leave commits, pull requests and issues unchanged.
- [ ] T024 [US2] In `backend/src/repositories/artifact_repository.py`, add: a method returning the existing `(identity, checksum, title, source_url, has_embedding)` for a workspace and source system; an upsert using `INSERT ... ON CONFLICT ON CONSTRAINT uq_artifact_identity DO UPDATE` with one path that rewrites content, checksum, embedding and `ingestion_version + 1` and one metadata-only path that leaves `embedding` untouched; and a method deleting stale pieces for given files using `startswith(prefix, autoescape=True)`.
- [ ] T025 [US2] In `backend/src/services/connector_svc.py`, compute SHA-256 of each piece's `content` into `checksum`, add the pure partition function tested in T018, embed only new and content-changed rows through the existing `asyncio.to_thread(embed_documents, ...)`, upsert, then delete stale pieces for each file seen, with the writes and the stale-piece deletion in one transaction. Update the class docstring.
- [ ] T026 [US2] In `backend/src/repositories/relationship_repository.py`, make `create` insert-or-ignore on `uq_relationship_edge` and then select the row so it still returns a `Relationship` (keep the signature). In `backend/src/services/relationship_svc.py`, count only newly created rows and remove the "accepts possible duplicate rows" sentence from the docstring.
- [ ] T027 [US2] Run T018 to T022 (now passing) plus the full existing suite, then `quickstart.md` scenarios 2 and 3.

**Checkpoint**: US2 complete (ADR-005). Retry (US4) is now safe to build.

---

## Phase 5: User Story 3 - Keyword search finds relevant artifacts (Priority: P2)

**Goal**: Natural-language questions match on their meaningful words, ranked, and keyword and vector results merge by rank fusion.

**Independent Test**: Fixed fixture artifacts and questions; compare keyword results to the T003 baseline and check merge ordering on hand-built overlaps.

**Depends on**: Phase 2 (search column), T003 (baseline committed).

### Tests for User Story 3 (write first, confirm they fail)

- [ ] T028 [P] [US3] Add `backend/tests/unit/test_keyword_query.py` for the question tokenizer: lower-cases and keeps letters and digits only, drops tokens under two characters, de-duplicates, caps at 12 tokens, returns no tokens for a question made only of punctuation or search-syntax characters (`"`, `-`, `&`, `(`, `)`, `:`, `|`), and for an empty string.
- [ ] T029 [P] [US3] Add `backend/tests/unit/test_rank_fusion.py` for reciprocal rank fusion: an artifact ranked first in both lists beats one ranked first in only one; an artifact in both lists appears once; the result is cut to the limit; ties are stable; empty inputs work.
- [ ] T030 [P] [US3] Add `backend/tests/integration/test_keyword_search.py`: an artifact containing "login" and "retry" in different sentences is returned for "how does the login retry work"; results are ordered by relevance; punctuation-only and syntax-character questions return without error; a stop-words-only question returns nothing without error; a second workspace's matching artifact is never returned.

### Implementation for User Story 3

- [ ] T031 [US3] In `backend/src/repositories/artifact_repository.py`, add the question tokenizer and rewrite `search_fulltext` to filter by `workspace_id`, build `to_tsquery('english', ' | '.join(tokens))`, match on `search_vector`, order by `ts_rank` descending, apply a limit, and return `[]` without querying when there are no tokens. Keep the method name and signature compatible with `test_workspace_isolation.py`.
- [ ] T032 [US3] In `backend/src/services/retrieval_svc.py`, give both retrieval calls the same limit and replace concatenation with a `reciprocal_rank_fusion` function using `RRF_K = 60`. Update the class docstring.
- [ ] T033 [US3] Confirm the open items in `research.md` §14 against a real database: how `to_tsvector('english', ...)` splits `get_by_id` and `spin_widget` (use `ts_debug`), and that a stop-words-only `to_tsquery` returns no rows and no error. Write the results into `research.md` §14.
- [ ] T034 (OWNER) [US3] Re-run `backend/scripts/keyword_baseline.py` on the new retrieval and add a before-and-after comparison to `specs/003-reliability-hardening/baseline.md`. Check SC-006: more questions find their expected artifact than at T003, and none that passed before now fail.

**Checkpoint**: US3 complete (ADR-006).

---

## Phase 6: User Story 4 - Temporary failures retry, final failures stay visible (Priority: P2)

**Goal**: Transient failures retry up to three attempts with increasing delays; the final error and attempt count stay visible; bad credentials are not retried.

**Independent Test**: Run jobs against a fake source that fails a set number of times and assert final status, attempts, delays and the status shown.

**Depends on**: Phase 2 and US2 (T027), so a retried run cannot duplicate data.

### Tests for User Story 4 (write first, confirm they fail)

- [ ] T035 [P] [US4] Add `backend/tests/unit/test_retry_policy.py`: `BACKOFF_SECONDS == (30, 120)`, `MAX_ATTEMPTS == 3`, each delay longer than the one before, `ConnectorAuthError` and `ValueError` classified permanent, other exceptions transient.
- [ ] T036 [P] [US4] Add `backend/tests/integration/test_ingest_retry.py` using a fake source and a controllable `next_attempt_at` (no real sleeping): fails twice then succeeds ends `complete` with `attempts == 3` and the connector never `failed`; always failing ends `failed` after exactly three attempts with the last error; a credential rejection ends `needs_reconnect` after one attempt with no retry; while retries remain the job is `queued` with a future `next_attempt_at` and the connector is `ingesting`; consecutive delays increase (SC-005).
- [ ] T037 [P] [US4] Add `backend/tests/contract/test_ingest_status.py` for the fields in `contracts/api.md`: job responses carry `attempts`, `max_attempts`, `next_attempt_at`; connector responses carry `ingestion_attempts`, `max_attempts`, `next_attempt_at`; all three are null for a connector that has never had a job; existing fields are unchanged.
- [ ] T038 [P] [US4] Add `frontend/src/app/status/__tests__/page.test.tsx`: while `status === "ingesting"` and `ingestion_attempts > 0` the page shows "Retrying (attempt N of M)" with the error in a muted style; when `failed` it shows the attempt count and the error in the failure style; polling continues through retries.

### Implementation for User Story 4

- [ ] T039 [US4] In `backend/src/repositories/job_repository.py`, add `schedule_retry(job, error_message, delay_seconds)` (status back to `queued`, `next_attempt_at = now + delay`, error kept) and `latest_for_connector(workspace_id, connector_id)`, and make `claim_oldest_queued` ignore jobs whose `next_attempt_at` is in the future.
- [ ] T040 [US4] In `backend/src/core/job_worker.py`, add `BACKOFF_SECONDS = (30, 120)`, `MAX_ATTEMPTS`, the permanent-versus-transient classification, and the decision in `_process_one`: permanent or final attempt means `mark_failed`; otherwise `schedule_retry`.
- [ ] T041 [US4] In `backend/src/services/ingestion_svc.py`, change `_handle_ingestion_job` so a transient failure sets the connector to `failed` only when this was the final attempt (`job.attempts >= MAX_ATTEMPTS`); otherwise keep it `ingesting` with the latest error in `error_message`. `ConnectorAuthError` still sets `needs_reconnect` on the first attempt.
- [ ] T042 [US4] Update the **fixtures only** of the two existing tests that fail a fresh job with a generic error and expect `failed`: `test_handle_ingestion_job_marks_connector_failed_on_error` in `backend/tests/unit/test_ingestion_svc.py` and `test_generic_failure_sets_failed_not_needs_reconnect` in `backend/tests/integration/test_ingestion_failure.py`. Set `job.attempts = MAX_ATTEMPTS` before calling the handler so the job is on its final attempt. Do not change any assertion. Add new test functions for the not-final case. (This is the one place an existing test's setup must change; note it in the commit message.)
- [ ] T043 [US4] In `backend/src/api/ingest.py` add `attempts`, `max_attempts` and `next_attempt_at` to `IngestJobResponse` and populate them in both endpoints. In `backend/src/api/connectors.py` add `ingestion_attempts`, `max_attempts` and `next_attempt_at` to `ConnectorStatusResponse`, filled from `latest_for_connector`, null when there is no job.
- [ ] T044 [US4] In `frontend/src/lib/api.ts` add the optional fields to `ConnectorStatusResponse` and `IngestJobResponse`. In `frontend/src/app/status/page.tsx` show the retry text and the muted error while `ingesting` with attempts, and the attempt count with the failure style when `failed`.
- [ ] T045 [US4] Run T035 to T038 (now passing), the existing suites, and `quickstart.md` scenario 5.

**Checkpoint**: US4 complete (ADR-007, retry part).

---

## Phase 7: User Story 5 - Two workers never run the same job (Priority: P3)

**Goal**: Each queued job is claimed by exactly one worker, and each connector has at most one active job.

**Independent Test**: Two concurrent workers against at least twenty queued jobs; each job runs once.

**Depends on**: T039 (same file and function as the claim change).

### Tests for User Story 5 (write first, confirm they fail)

- [ ] T046 [P] [US5] Add `backend/tests/integration/test_job_claiming.py`: at least twenty queued jobs and two workers claiming concurrently with `asyncio.gather` on separate sessions; assert every job's execution count is exactly one, repeated several times (SC-004); one queued job and two simultaneous claims yields exactly one success and one `None`; a `running` job is never claimed by the other worker.
- [ ] T047 [P] [US5] Add `backend/tests/integration/test_single_active_job.py`: a second trigger for a connector with a queued, running or waiting-to-retry job returns the existing job and creates none; a `running` job older than 60 minutes is marked `failed` ("abandoned: worker stopped") at enqueue and a new job is created; a `running` job younger than 60 minutes is not swept.

### Implementation for User Story 5

- [ ] T048 [US5] In `backend/src/repositories/job_repository.py`, make `claim_oldest_queued` a single `SELECT ... FOR UPDATE SKIP LOCKED` (via `with_for_update(skip_locked=True)`) honouring `next_attempt_at`, with the status update in the same transaction.
- [ ] T049 [US5] In `backend/src/repositories/job_repository.py`, make `enqueue` first mark `running` jobs for that connector older than `STALE_RUNNING_AFTER` (60 minutes) as `failed`, then insert, and on a unique-index conflict return the existing active job. Keep the positional signature the existing tests use. In `backend/src/services/ingestion_svc.py` make `trigger` handle a returned existing job without resetting the connector status incorrectly.
- [ ] T050 [US5] Run T046 and T047 (now passing), the existing suites, and `quickstart.md` scenario 6.

**Checkpoint**: US5 complete (ADR-007, claiming part).

---

## Phase 8: Polish and cross-cutting

**Purpose**: Documentation required by FR-027, full regression, and final validation.

- [ ] T051 [P] Update `README.md` "Known limitations": remove the substring-search, no-retry, unsafe-claim and unescaped-evidence items that are now fixed, and keep the ones that remain (full re-ingestion only, no upstream-deletion handling, abandoned-job sweep is minimal, adversarial testing against the live model not done).
- [ ] T052 [P] Update `docs/roadmap.md`: mark Phase 2's "basic ingestion error handling and retry behavior" done, and note which Phase 3 items this feature pulled forward (retrieval observability and live-model adversarial tests remain open).
- [ ] T053 [P] Add a "Superseded in part by ADR-007" note to the Consequences of `docs/decisions/ADR-001-weekend-mvp-stack.md`, and add a one-line pointer to `specs/003-reliability-hardening/data-model.md` in `specs/001-trace-doc-to-code/data-model.md` for the changed identity and checksum meaning.
- [ ] T054 [P] Add a resolved entry for re-ingestion idempotency to `docs/prd.md` §10, pointing to ADR-005 and this spec (the old code comment cited a PRD open question that was never written there).
- [ ] T055 Run the full regression: `uv run pytest`, `uv run ruff check .` in `backend/`; `pnpm test`, `pnpm lint` in `frontend/`. Then run `git diff main -- backend/tests frontend/src` and confirm the only changes to existing tests are fixture data from T012 and T042 and added tests, with no assertion line changed (SC-007).
- [ ] T056 Run every scenario in `quickstart.md` (0 to 7) and write the results, with counts, in `specs/003-reliability-hardening/validation.md`.
- [ ] T057 Change ADR-005, ADR-006, ADR-007 and ADR-008 from "Proposed" to "Accepted" and set the spec status to Approved, once T056 passes.
- [ ] T058 (OWNER) Review `validation.md` and `migration-rehearsal.md`, then decide whether to apply the migration to the real database and re-ingest each connector so code files return.

---

## Dependencies and execution order

```text
Phase 1 Setup:       T001 → T003 → (blocks T031, T032)         T002, T004, T005 anytime
Phase 2 Foundation:  T006 → T007,T008,T009 [P] → T010 → T011 → T012 → (T013 blocks real-DB migration only)
US1 (Phase 3):       independent of Phase 2; T014,T015 [P] → T016 → T017
US2 (Phase 4):       after T012;  T018–T022 [P] → T023 → T024 → T025 → T026 → T027
US3 (Phase 5):       after T012 and T003;  T028–T030 [P] → T031 → T032 → T033 → T034
US4 (Phase 6):       after T027;  T035–T038 [P] → T039 → T040 → T041 → T042 → T043 → T044 → T045
US5 (Phase 7):       after T039;  T046,T047 [P] → T048 → T049 → T050
Polish (Phase 8):    after all stories;  T051–T054 [P] → T055 → T056 → T057 → T058
```

**Story independence**: US1 touches no database and can ship alone. US2, US3 and US4/US5 each depend only on Phase 2, except US4 which also needs US2. US3 and US2 can run in parallel after Phase 2 because they edit different methods, though both edit `artifact_repository.py` (T024 and T031), so merge those two tasks one after the other.

**Files touched by more than one task (do not parallelize)**: `backend/src/repositories/artifact_repository.py` (T024, T031), `backend/src/repositories/job_repository.py` (T039, T048, T049), `backend/src/services/ingestion_svc.py` (T041, T049).

## Parallel examples

```text
US1 tests:   T014 and T015 together
US2 tests:   T018, T019, T020, T021 and T022 together
US3 tests:   T028, T029 and T030 together
US4 tests:   T035, T036, T037 and T038 together
Models:      T007, T008 and T009 together
Docs:        T051, T052, T053 and T054 together
```

## Implementation strategy

1. **MVP**: Phase 3 (US1, escaping) alone. It needs no migration, has the clearest security payoff, and can ship before anything else.
2. **Then** record the baseline (T001 to T003) and finish Phase 2, including the real-data rehearsal (T013), because everything else sits on that migration.
3. **Then** US2 (P1) and US3 (P2), then US4, then US5 (P3).
4. Stop and validate at each checkpoint. Each story is independently demonstrable; only US4 depends on another story (US2).
5. Do not apply the migration to a non-scratch database until T013 is reviewed.
