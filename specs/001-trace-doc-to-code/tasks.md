# Tasks: Trace a Spec/Doc to Code

**Input**: Design documents from `/specs/001-trace-doc-to-code/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/api.md, quickstart.md — all present.

**Tests**: Included. Not optional here — CLAUDE.md's coding conventions and the spec-driven sequence in the constitution (`code → tests → validation`) require them; this isn't a default I'm overriding without reason.

**Organization**: Tasks are grouped by user story (from spec.md) so each story is independently implementable, testable, and demoable.

**Revision note (post `/speckit-analyze`)**: T020 and T023/T041 now build in token encryption (FR-016) and untrusted-content isolation (FR-015) at the point those files are first created, instead of deferring both to Polish — the original ordering meant the MVP checkpoint (end of Phase 3) would have shipped with plaintext tokens and unverified prompt isolation, violating Constitution Principle III. T057/T058 are now regression checks confirming that behavior, not the first implementation of it. T031 was added to cover spec.md's US1 Acceptance Scenario 3, which had no test coverage in the original task list. All task IDs from T031 onward shifted by +1 to make room.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependency on an incomplete task)
- **[Story]**: Maps to spec.md's US1/US2/US3
- Paths follow the Web application structure from plan.md (`backend/src/`, `frontend/src/`)

---

## Phase 1: Setup

- [X] T001 Create `backend/` and `frontend/` directories per plan.md's Project Structure
- [X] T002 Initialize backend: `uv init`, add FastAPI, Pydantic v2, SQLAlchemy 2.0, Alembic, `pgvector`, Groq SDK, Voyage SDK, `supabase-py`, `httpx`, `notion-client`, `pytest`, `pytest-asyncio` to `backend/pyproject.toml`
- [X] T003 [P] Initialize frontend: Next.js 15 (App Router, TypeScript, Tailwind) via `pnpm create next-app` in `frontend/`, add shadcn/ui, `vitest`, React Testing Library
- [X] T004 [P] Configure `ruff` (lint + format) in `backend/pyproject.toml`
- [X] T005 [P] Configure `eslint` + `prettier` in `frontend/`
- [X] T006 Create `.env.example` at repo root listing `DATABASE_URL`, `SUPABASE_URL`, `SUPABASE_JWT_SECRET`, `GROQ_API_KEY`, `VOYAGE_API_KEY`, `GITHUB_TOKEN`, `NOTION_TOKEN` (per quickstart.md Prerequisites)

---

## Phase 2: Foundational (Blocking Prerequisites)

**⚠️ CRITICAL**: No user story work begins until this phase is complete.

- [X] T007 Configure SQLAlchemy engine/session in `backend/src/core/db.py`
- [X] T008 Configure Alembic migrations framework in `backend/alembic/`
- [X] T009 [P] Create Workspace model in `backend/src/models/workspace.py` (data-model.md)
- [X] T010 [P] Create Connector model in `backend/src/models/connector.py`, including the `(workspace_id, source_system)` unique constraint
- [X] T011 [P] Create Artifact model (with `pgvector` embedding column) in `backend/src/models/artifact.py`, `source_url` non-nullable
- [X] T012 [P] Create Relationship model in `backend/src/models/relationship.py`, with a DB check constraint restricting `relationship_origin` to `explicit`/`metadata-derived` for any row written by Phase 1 code paths
- [X] T013 [P] Create Job model in `backend/src/models/job.py`
- [X] T014 Generate and apply the initial Alembic migration for all 5 tables (depends on T009-T013)
- [X] T015 Implement Supabase JWT verification dependency in `backend/src/core/auth.py` (research.md §2)
- [X] T016 Implement FastAPI app entrypoint and router registration in `backend/src/main.py`
- [X] T017 [P] Implement `workspace_repository` in `backend/src/repositories/workspace_repository.py`
- [X] T018 [P] Implement `artifact_repository` in `backend/src/repositories/artifact_repository.py`
- [X] T019 [P] Implement `relationship_repository` in `backend/src/repositories/relationship_repository.py`
- [X] T020 [P] Implement `connector_repository` in `backend/src/repositories/connector_repository.py`, **encrypting the access token before every write and decrypting only at the point of use — a connector row is never persisted with a plaintext token, even transiently** (FR-016, Constitution Principle III)
- [X] T021 [P] Implement `job_repository` in `backend/src/repositories/job_repository.py`
- [X] T022 Implement the in-process job-worker polling loop in `backend/src/core/job_worker.py`, started on app startup (research.md §1; depends on T021)
- [X] T023 [P] Implement the Groq client (single-provider interface) in `backend/src/llm/groq_client.py`, **structuring every request so retrieved content is passed as a distinct data parameter, never string-concatenated into the system prompt** (FR-015, Constitution Principle III)
- [X] T024 [P] Implement the Voyage embeddings client in `backend/src/llm/voyage_client.py`
- [X] T025 [P] Implement the base connector interface (`authenticate`, `ingest_full`, `normalize_artifact`, `normalize_relationship`, `health_check`) in `backend/src/connectors/base.py`
- [X] T026 [P] Scaffold the Next.js app shell and typed REST client skeleton in `frontend/src/lib/api.ts`
- [X] T027 [P] Implement the shared error-response shape (contracts/api.md) as FastAPI exception handlers in `backend/src/api/errors.py`

**Checkpoint**: Foundation ready — user story work can begin.

---

## Phase 3: User Story 1 - Connect tools and get a cited answer (Priority: P1) 🎯 MVP

**Goal**: A user signs in, creates a workspace, connects GitHub + Notion, and gets one cited, evidence-backed answer.

**Independent Test**: quickstart.md scenarios 1-3, against a real small repo + Notion page with a known deterministic link.

### Tests for User Story 1

> Write these first; confirm they fail before implementation.

- [X] T028 [P] [US1] Contract test for `POST /workspaces` in `backend/tests/contract/test_workspaces.py`
- [X] T029 [P] [US1] Contract test for `POST /connectors/github` and `POST /connectors/notion` in `backend/tests/contract/test_connectors.py`
- [X] T030 [P] [US1] Contract test for `POST /ask` deterministic-citation case in `backend/tests/contract/test_ask.py`
- [X] T031 [P] [US1] Integration test covering quickstart.md scenario 3 — no deterministic link exists, response either returns a citation with `origin: "inferred"` or explicitly abstains, never presents the inferred match as certain — in `backend/tests/integration/test_trace_doc_no_link.py`
- [X] T032 [P] [US1] Integration test covering quickstart.md scenarios 1-2 end-to-end (connect + ingest, deterministic citation) in `backend/tests/integration/test_trace_doc_flow.py`

### Implementation for User Story 1

- [X] T033 [US1] Implement `workspace_svc` (create workspace, enforce one workspace per user) in `backend/src/services/workspace_svc.py` (depends on T017)
- [X] T034 [US1] Implement `GitHubConnector` (auth, `ingest_full`: files/PRs/commits/issues/contributors, `normalize_artifact`) in `backend/src/connectors/github_connector.py` (depends on T025)
- [X] T035 [US1] Implement `NotionConnector` (auth, `ingest_full`: selected pages/blocks, `normalize_artifact`) in `backend/src/connectors/notion_connector.py` (depends on T025)
- [X] T036 [US1] Implement code chunking (function/class-boundary via `ast` for Python, heuristic boundary split for TS/JS, flat-text fallback otherwise) in `backend/src/services/chunking.py` (research.md §3)
- [X] T037 [US1] Implement `connector_svc` (dispatch to GitHub/Notion connectors, persist Connector rows, chunk + embed ingested content via `voyage_client`) in `backend/src/services/connector_svc.py` (depends on T034, T035, T036, T024)
- [X] T038 [US1] Implement `relationship_svc` deterministic-link extraction (bidirectional regex URL matching) in `backend/src/services/relationship_svc.py` (research.md §4)
- [X] T039 [US1] Implement `ingestion_svc` (enqueues Job rows; job worker calls `connector_svc.ingest` then `relationship_svc` extraction) in `backend/src/services/ingestion_svc.py` (depends on T037, T038, T022)
- [X] T040 [US1] Implement `retrieval_svc` (full-text + `pgvector` similarity search over artifacts) in `backend/src/services/retrieval_svc.py` (depends on T011)
- [X] T041 [US1] Implement `answer_svc` (grounded generation via `groq_client`, `origin` labeling per citation, deterministic-first evidence ordering — retrieved evidence assembled into a distinct evidence packet passed to `groq_client` as data, never merged into prompt instructions, per FR-015/Constitution Principle III) in `backend/src/services/answer_svc.py` (depends on T040, T023, T038)
- [X] T042 [US1] Implement `POST /connectors/github`, `POST /connectors/notion`, `GET /connectors/{id}/status` in `backend/src/api/connectors.py` (depends on T037)
- [X] T043 [US1] Implement `POST /ingest/{connector_id}`, `GET /ingest/{job_id}/status` in `backend/src/api/ingest.py` (depends on T039)
- [X] T044 [US1] Implement `POST /ask` in `backend/src/api/ask.py` (depends on T041)
- [X] T045 [US1] Implement the Workspace page (sign in, create workspace) in `frontend/src/app/page.tsx` (depends on T026)
- [X] T046 [US1] Implement the Connectors page in `frontend/src/app/connect/page.tsx` (depends on T042)
- [X] T047 [US1] Implement the Ask page (submit question, render answer + citations with origin badges) in `frontend/src/app/ask/page.tsx` (depends on T044)

**Checkpoint**: User Story 1 is fully functional and independently testable — run quickstart.md scenarios 1-3. Because T020/T023/T041 now build in encryption and content isolation from the start, this checkpoint satisfies FR-015/FR-016 without waiting for Polish.

---

## Phase 4: User Story 2 - Evidence discipline: abstain rather than guess (Priority: P2)

**Goal**: The system never presents an unsupported claim as fact, and abstains explicitly when evidence is missing.

**Independent Test**: quickstart.md scenarios 4-5.

### Tests for User Story 2

- [ ] T048 [P] [US2] Contract test for `POST /ask` abstention case (no relevant evidence) in `backend/tests/contract/test_ask_abstain.py`
- [ ] T049 [P] [US2] Integration test proving citation validation rejects any citation not in the retrieved evidence set in `backend/tests/integration/test_citation_validation.py`

### Implementation for User Story 2

- [ ] T050 [US2] Add server-side citation validation to `answer_svc` — strip/reject any citation whose artifact wasn't actually retrieved for this request (FR-013) in `backend/src/services/answer_svc.py` (extends T041)
- [ ] T051 [US2] Add the abstention branch to `answer_svc` when retrieval returns no evidence above a minimum relevance bar (FR-012) in `backend/src/services/answer_svc.py` (extends T041)
- [ ] T052 [US2] Surface the abstained state and reason in the Ask page UI in `frontend/src/app/ask/page.tsx` (extends T047)

**Checkpoint**: US1 + US2 both work independently — run quickstart.md scenarios 1-5.

---

## Phase 5: User Story 3 - Ingestion status visibility (Priority: P3)

**Goal**: A user can tell whether their connected tools finished ingesting or failed.

**Independent Test**: quickstart.md scenario 6.

### Tests for User Story 3

- [ ] T053 [P] [US3] Contract test for `GET /connectors/{id}/status` transitions in `backend/tests/contract/test_connector_status.py`
- [ ] T054 [P] [US3] Integration test: forced ingestion failure surfaces a non-null `error_message` in `backend/tests/integration/test_ingestion_failure.py`

### Implementation for User Story 3

- [ ] T055 [US3] Add failure / `needs_reconnect` status handling and `error_message` capture to `ingestion_svc` and `job_worker` in `backend/src/services/ingestion_svc.py`, `backend/src/core/job_worker.py` (extends T039, T022)
- [ ] T056 [US3] Implement the Ingestion status page (polls connector/job status, renders in-progress/complete/failed) in `frontend/src/app/status/page.tsx` (depends on T042, T043)

**Checkpoint**: All three user stories independently functional — run the full quickstart.md.

---

## Phase 6: Polish & Cross-Cutting Concerns

- [ ] T057 [P] **Regression check**: verify `connector_repository` (T020) never persists a plaintext token — add a test asserting the stored value differs from the raw input and round-trips correctly through decryption, in `backend/tests/unit/test_token_encryption.py`
- [ ] T058 [P] **Regression check**: verify `answer_svc`/`groq_client` (T041, T023) isolation — add a test asserting retrieved artifact content never appears inside the system-prompt string sent to the model, in `backend/tests/unit/test_prompt_isolation.py`
- [ ] T059 [P] Add workspace-isolation tests across all repositories (Constitution Principle VI) in `backend/tests/unit/test_workspace_isolation.py`
- [ ] T060 Update `docs/roadmap.md`'s Phase 1 checklist and `CLAUDE.md`'s Commands section with real backend/frontend commands now that both exist
- [ ] T061 Run the full quickstart.md validation pass — all 6 scenarios, ≥10 hand-written questions total (PRD §7 SC-002/SC-003)
- [ ] T062 Verify Groq's free-tier rate limits are understood (no spend cap needed — there's no billing relationship, ADR-002) and Voyage usage limits are configured before any real ingestion run

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: no dependencies
- **Foundational (Phase 2)**: depends on Setup — blocks all user stories
- **User Story 1 (Phase 3)**: depends on Foundational only
- **User Story 2 (Phase 4)**: depends on Foundational; extends US1's `answer_svc`/Ask page rather than duplicating them, so build it after US1 even though the underlying data doesn't strictly require it
- **User Story 3 (Phase 5)**: depends on Foundational; extends US1's `ingestion_svc`/job worker and connector endpoints
- **Polish (Phase 6)**: depends on all three user stories being complete

### Within Each User Story

- Tests are written and confirmed failing before implementation
- Models (Phase 2, shared) → repositories (Phase 2) → services → endpoints → frontend pages
- Story complete and independently validated before moving to the next priority

### Parallel Opportunities

- All `[P]` tasks within Phase 1 and Phase 2 can run in parallel (different files, no interdependency)
- T028-T032 (US1 tests) can run in parallel with each other, but must all exist and fail before T033+ begins
- T048-T049 (US2 tests) and T053-T054 (US3 tests) can be written in parallel with each other once Phase 3 is complete

---

## Parallel Example: Phase 2 Foundational

```bash
Task: "Create Workspace model in backend/src/models/workspace.py"
Task: "Create Connector model in backend/src/models/connector.py"
Task: "Create Artifact model in backend/src/models/artifact.py"
Task: "Create Relationship model in backend/src/models/relationship.py"
Task: "Create Job model in backend/src/models/job.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Phase 1: Setup
2. Phase 2: Foundational (blocks everything else)
3. Phase 3: User Story 1
4. **Stop and validate** against quickstart.md scenarios 1-3 before continuing
5. This is the demoable MVP referenced throughout docs/prd.md and docs/roadmap.md Phase 1 — and, per the revision note above, it's now a checkpoint that doesn't compromise on security to get there

### Incremental Delivery

1. Setup + Foundational → foundation ready
2. User Story 1 → validate → this is the MVP
3. User Story 2 → validate → evidence discipline proven
4. User Story 3 → validate → ingestion status visible
5. Polish → full quickstart.md pass, plus regression checks confirming T020/T023/T041's security properties still hold, and budget verification

---

## Notes

- `[P]` = different files, no dependency on an incomplete task
- Commit after each task or logical group (per CLAUDE.md conventions — no `Co-Authored-By` trailer)
- Stop at each checkpoint and actually run the relevant quickstart.md scenario before moving on — don't just mark tasks complete on faith
