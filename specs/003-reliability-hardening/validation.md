# Validation: 003 Reliability hardening

Run on the owner's machine (scratch database `contextos_test`, Postgres 17 on port 5433) at
commit 6d40ff1 unless stated. **Status: in progress.** Rows marked "pending" still need a run.

## Automated results

| Check | Result |
|---|---|
| Backend `uv run pytest` | 153 passed, 8 skipped (the 8 are the migration tests, which need `MIGRATION_TEST_DATABASE_URL`) |
| Migration tests with that variable set | 8 passed (earlier run, before the formatting-only commit) |
| Backend `uv run ruff check .` / `ruff format --check .` | All checks passed; 82 files formatted |
| Frontend `pnpm test` | 2 files, 6 tests passed |
| Frontend `pnpm lint` | eslint clean (no findings) |
| Local Postgres version (T004) | 17.10; the hosted Supabase version is not yet checked |
| Existing tests unchanged (SC-007) | `git diff origin/main --diff-filter=M -- backend/tests frontend/src` shows only added lines and the fixture line `job.attempts = MAX_ATTEMPTS`; no assertion removed or edited |
| Start-commit backend suite (T005) | 90 passed on `main` before this feature |

## Quickstart scenarios

| # | Scenario | Result |
|---|---|---|
| 0 | Keyword baseline | Done. 0 of 16 before (commit 0aea7e5). See `baseline.md` |
| 1 | Evidence cannot be broken out of | Passed: `test_evidence_escaping.py` (11 breakout patterns, neighbours undisturbed) and `test_cite_marker_in_evidence.py` |
| 2 | Re-ingest twice, no change | Tests pass (`test_idempotent_ingestion.py`). Real-data text-only re-run on the copy: 588 artifacts and 1 relationship before and after, 0 new relationships. The "0 texts embedded" proof on real data is pending a full run with embeddings |
| 3 | One change at the source | Tests pass (`test_ingestion_changes.py`) |
| 4 | Keyword search on natural questions | **12 of 16 found, up from 0 of 16; none regressed (SC-006).** See `baseline.md` |
| 5 | Retry and visibility | Tests pass (`test_retry_policy.py`, `test_ingest_retry.py`, `test_ingest_status.py`, status page tests). Live check on the status page: pending |
| 6 | Two workers | Tests pass (`test_job_claiming.py`, `test_single_active_job.py`) |
| 7 | Migration on a copy of real data | Done on `contextos_dev_copy`: 2,060 artifacts and 585 duplicate identities before; 214 artifacts and 0 duplicates after. See `migration-rehearsal.md` |

## Open items

- A full re-ingest with embeddings on the copy, showing the second run sends 0 texts.
- Live status-page check of a retrying connector.
- Owner review (T058) and the decision on applying the migration to the real database.
