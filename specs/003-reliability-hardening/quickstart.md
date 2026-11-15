# Quickstart: Validate Phase 1 Reliability Hardening

A run guide for proving each requirement works. It is not a test suite; the automated tests are listed in `tasks.md`. Contracts and data model details are in `contracts/api.md` and `data-model.md`.

## Prerequisites

- The local scratch database and backend setup from `CLAUDE.md` ("Local scratch database"), with PostgreSQL 12 or later (local is 17). Confirm the hosted Supabase project's version before deploying.
- A local database that has been ingested at least twice, so it contains real duplicates. Do not run the migration on it until scenario 0 and scenario 7 are done.
- Backend `.env` with the same keys as feature 001's quickstart.
- Record the commit you start from; scenario 0 must run on code that has none of this feature's retrieval changes.

## Scenario 0: Record the keyword-search baseline (do this first)

1. Write about ten real questions about your own repo and Notion pages, each paired with the URL of the artifact that should be found.
2. Against the current database and the unmodified retrieval code, run each question through keyword retrieval only and record whether the expected artifact appears in the first ten results.
3. Save questions, expected URLs and results to `specs/003-reliability-hardening/baseline.md`.

**Expected**: a committed baseline. SC-006 compares against it. No later step may begin before this exists.

## Scenario 1: Evidence cannot be broken out of (User Story 1)

1. Run the adversarial unit tests for evidence rendering.
2. Optionally ingest a Notion page containing a closing evidence tag followed by an instruction, ask a question that retrieves it, and confirm the answer does not follow the instruction.

**Expected**: every pattern in the adversarial set (at least eight) leaves one evidence section and the same number of items as were retrieved; item attributes keep their true values (SC-003). The existing prompt-isolation and citation tests pass unchanged.

## Scenario 2: Re-ingest twice with no change (User Story 2)

1. Take a copy of the migrated database (scenario 7), connect a connector, ingest, and record the artifact and relationship counts.
2. Ingest the same connector again, with nothing changed at the source.

**Expected**: both counts are identical and the embedding service receives zero requests on the second run (SC-001).

## Scenario 3: One change at the source (User Story 2)

1. Edit one file in the connected repo (or one Notion page) and ingest again.

**Expected**: exactly one artifact's content changes (more than one row only if the edited file is split into pieces), only those pieces are re-embedded, `ingestion_version` increases for them, and no old version of the file remains searchable (SC-002). Make the same file shorter so it has fewer pieces and ingest again: leftover pieces are gone.

## Scenario 4: Keyword search on a natural question (User Story 3)

1. Re-run the baseline questions from scenario 0 through the new keyword retrieval.
2. In `psql`, check how the search configuration tokenizes a code identifier (`ts_debug`) and run a stop-words-only query.
3. Ask a question made only of punctuation and search-syntax characters.

**Expected**: more baseline questions find their expected artifact than before, and none that passed before now fail (SC-006). The stop-words query returns nothing without an error. The punctuation-only question returns normally and similarity results still answer it.

## Scenario 5: Retry and visibility (User Story 4)

1. Use the retry tests, which fail a fake source a set number of times, to confirm: two failures then success ends `complete` after three attempts; always failing ends `failed` after three attempts with the last error; a rejected credential ends `needs_reconnect` after one attempt (SC-005).
2. In the running app, point a connector at an unreachable source and watch the status page.

**Expected**: the page shows "Retrying (attempt N of 3)" with a muted error while retries remain, then the failure style with the attempt count after the last attempt. Delays between attempts increase.

## Scenario 6: Two workers (User Story 5)

1. Run the concurrent-claim test: at least twenty queued jobs, two workers polling at once.

**Expected**: every job ran exactly once, in repeated runs (SC-004). A second trigger for the same connector while one is active returns the existing job.

## Scenario 7: Rollout migration on a copy of real data (do before touching real data)

1. Copy the real database. For the local database: `createdb -p 5433 -T contextos_dev contextos_dev_copy`. For a hosted database: `pg_dump` and restore into a scratch database.
2. Before migrating the copy, record: artifact count, count of identities with more than one row, relationship count, count of connectors with more than one active job.
3. Run `uv run alembic upgrade head` against the copy.
4. Record the same counts again, then re-ingest each connector on the copy.

**Expected**: no identity has more than one row; relationship count dropped only by true duplicates; every relationship that existed between a document and a pull request or commit still exists after re-ingest; no connector has more than one active job. Review these numbers before running the migration on the real database. The migration deletes rows, so keep the backup until the re-ingest is confirmed good.

## Full regression

Run the whole backend test suite (`uv run pytest`) and the frontend tests (`pnpm test`). Existing assertions must pass unchanged (FR-026). Only two kinds of fixture change are allowed in existing tests: artifact identity values where a fixture reuses an identity (tasks T012), and the job's attempt count in the two tests that fail a fresh job with a generic error and expect the connector to be `failed` (`test_handle_ingestion_job_marks_connector_failed_on_error` and `test_generic_failure_sets_failed_not_needs_reconnect`; task T042). Those two jobs must be set to their final attempt, because a first failure now retries instead of failing the connector.
