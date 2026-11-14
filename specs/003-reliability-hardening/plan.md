# Implementation Plan: Phase 1 Reliability Hardening

**Branch**: `003-reliability-hardening` | **Date**: 2026-11-14 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/003-reliability-hardening/spec.md`

## Summary

Close five known Phase 1 reliability gaps without changing product scope. The approach stays inside PostgreSQL and the existing stack:

1. **Escape** every field of retrieved content before it enters the model request.
2. **Idempotent ingestion**: stable artifact identity (file path, not blob SHA), a service-computed content hash, and an upsert that embeds only new or changed content. A one-time migration collapses existing duplicates.
3. **Ranked keyword search** from a stored full-text column with an OR query, merged with vector results by reciprocal rank fusion.
4. **Bounded retry with backoff**, represented as a queued job with a future `next_attempt_at`, so no enum changes are needed.
5. **Safe claiming** with `FOR UPDATE SKIP LOCKED`, one active job per connector, and a minimal abandoned-job sweep so the new uniqueness rule cannot strand a connector.

Design rationale and rejected alternatives are in [research.md](research.md); four short ADRs record the real trade-offs. The first piece of work is recording the keyword-search baseline, which needs the owner to write the question set.

## Technical Context

**Language/Version**: Python 3.12 (backend); TypeScript (status page only)

**Primary Dependencies**: no additions. Existing FastAPI, SQLAlchemy 2.0 async, Alembic, pgvector, Groq and Voyage clients. New code uses only the standard library (`html`, `re`, `hashlib`) and SQLAlchemy's PostgreSQL dialect (`insert ... on_conflict_do_update`, `with_for_update(skip_locked=True)`).

**Storage**: PostgreSQL 12 or later (generated columns). Local scratch database is 17; the hosted Supabase version must be confirmed (quickstart prerequisites).

**Testing**: `pytest` against a real PostgreSQL with pgvector for ingestion, claiming, migration and search; plain unit tests for escaping, fusion and retry policy; `vitest` for the status page.

**Target Platform**: unchanged (local development; hosted deployment is not part of this feature).

**Project Type**: web application (existing `backend/` and `frontend/`).

**Performance Goals**: no new throughput targets. A re-ingest with no source changes makes zero embedding requests; keyword search is served by an index and returns at most the configured limit.

**Constraints**: $0 and no new external service or paid dependency (constitution); no PostgreSQL enum changes; existing test assertions must pass unchanged.

**Scale/Scope**: one repo, one Notion source, hundreds to low thousands of artifacts.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-checked after Phase 1 design.*

| Principle | Status | Notes |
|---|---|---|
| I. Evidence-Backed Answers (NON-NEGOTIABLE) | Pass | Citation validation and abstention are untouched (FR-004). Fewer duplicates and better retrieval improve the evidence the validator checks against. |
| II. Deterministic Before Inferred | Pass | Relationship extraction still writes only explicit and metadata-derived links; only uniqueness changes. |
| III. Untrusted Content Boundary | Pass, strengthened | Escaping closes a demonstrated break-out (research.md §12). |
| IV. Spec-Driven Development | Pass | This plan follows an approved-for-planning spec; ADR-005 to ADR-008 record the trade-offs before code. |
| V. Narrowest Credible Scope | Pass with one note | No feature surface is added. The abandoned-job sweep is the only item beyond the five requirements; it is required because the one-active-job rule would otherwise make a crashed job permanent (Complexity Tracking). |
| VI. Workspace Isolation | Pass | Every new query filters by `workspace_id`. Job claiming remains cross-workspace by design, as today. Both retrieval paths are tested for isolation (FR-016). |
| Technology Constraints ($0, no new service) | Pass | PostgreSQL built-ins only; no new dependency, so no new-dependency ADR is required. |

**Post-design re-check**: unchanged. Two items carry residual risk and are tracked as tasks: fixtures that reuse an artifact identity may need distinct IDs (research.md §14), and the migration deletes rows and must be rehearsed on a copy first.

## Project Structure

### Documentation (this feature)

```text
specs/003-reliability-hardening/
├── spec.md
├── plan.md              # This file
├── research.md          # Phase 0
├── data-model.md        # Phase 1
├── quickstart.md        # Phase 1
├── contracts/
│   └── api.md           # Phase 1 (additive changes only)
├── checklists/
│   └── requirements.md
├── baseline.md          # Recorded by the first task, before any retrieval change
└── tasks.md             # /speckit-tasks output

docs/decisions/
├── ADR-005-idempotent-ingestion.md
├── ADR-006-postgres-fulltext-and-rank-fusion.md
├── ADR-007-job-retry-claiming-and-single-active-job.md
└── ADR-008-escape-retrieved-content.md
```

### Source Code (repository root)

```text
backend/
├── scripts/
│   └── keyword_baseline.py                         # runs the baseline questions through keyword search, before and after
├── alembic/versions/
│   └── <new revision>_reliability_hardening.py     # cleanup, constraints, columns, index
├── src/
│   ├── connectors/github_connector.py              # source file identity: path, not blob SHA
│   ├── core/job_worker.py                          # retry decision, backoff constants
│   ├── llm/groq_client.py                          # escape evidence; one system-prompt sentence
│   ├── models/{artifact,relationship,job}.py       # constraints, search_vector, next_attempt_at
│   ├── repositories/
│   │   ├── artifact_repository.py                  # existing-state lookup, upsert, stale-piece delete, ranked keyword search
│   │   ├── relationship_repository.py              # create becomes insert-or-ignore
│   │   └── job_repository.py                       # skip-locked claim, schedule retry, idempotent enqueue, stale sweep, latest job lookup
│   ├── services/
│   │   ├── connector_svc.py                        # hash, partition, embed changed only, upsert
│   │   ├── ingestion_svc.py                        # connector status only on final failure
│   │   ├── relationship_svc.py                     # count only new relationships
│   │   └── retrieval_svc.py                        # reciprocal rank fusion
│   └── api/{ingest,connectors}.py                  # additive response fields
└── tests/
    ├── unit/                                       # escaping (adversarial set), fusion, retry policy, query tokenizer
    ├── integration/                                # idempotent ingestion, stale pieces, claiming, retry flow, keyword search, migration
    └── contract/                                   # status response fields

frontend/
└── src/
    ├── lib/api.ts                                  # optional new fields
    └── app/status/page.tsx                         # retry display, muted error while retrying
```

**Structure Decision**: modify the existing web-application layout in place. No new top-level directories, services or modules. Reciprocal rank fusion lives in `retrieval_svc.py` as one small function.

## Work order

1. **Baseline** (blocks all retrieval changes): the owner writes the question set; record `baseline.md` (quickstart scenario 0).
2. **Escaping** (independent, smallest): ADR-008, tests first, then the change.
3. **Idempotent ingestion**: ADR-005; identity change in the GitHub connector; hash, partition and upsert; stale-piece cleanup; relationship insert-or-ignore.
4. **Rollout migration**: written and rehearsed on a copy (quickstart scenario 7) before it is applied anywhere real. It adds the constraints that step 3's behavior relies on, so it ships with step 3.
5. **Search and fusion**: ADR-006; generated column and index (in the same migration); tokenizer, ranked query, fusion; re-run the baseline.
6. **Jobs**: ADR-007; skip-locked claim, retry state and policy, one-active-job rule and sweep, status fields, status page. Retry depends on step 3 being done, so a retried run cannot duplicate data.
7. **Docs**: update `README.md` Known limitations, `docs/roadmap.md`, and ADR-001's consequences in the same change that alters the behavior (FR-027).

## Complexity Tracking

| Item | Why Needed | Simpler Alternative Rejected Because |
|---|---|---|
| Abandoned-job sweep at enqueue (60 minutes) | The one-active-job rule would turn a job stuck in `running` after a crash into a permanent block on that connector, which is worse than today | Doing nothing regresses the crash case that the spec says must not be made worse. A full lease and heartbeat system is out of scope. Overlap from a wrongly swept healthy job is harmless because ingestion is idempotent. |
| Deleting legacy GitHub source-file artifacts in the migration | Their identity (blob SHA) cannot be mapped to the new identity (path) reliably, and old versions would leave stale pieces | Re-keying from `source_url` is fragile and keeps stale pieces. The data is rebuilt by the next ingest, which re-embeds files as every ingest does today. |
| Four ADRs for one feature | Constitution requires an ADR for each real trade-off, and these four are independent decisions | One combined ADR would hide which decision a later change is revisiting. Each ADR is kept short. |
