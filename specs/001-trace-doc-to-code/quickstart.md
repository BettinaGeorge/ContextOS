# Quickstart: Validate "Trace a Spec/Doc to Code"

A runnable guide to prove the feature works end-to-end against the acceptance scenarios in `spec.md`. Not a tutorial — this is what "done" gets checked against.

## Prerequisites

- A Supabase project (free tier) with the pgvector extension enabled — provides `DATABASE_URL`, `SUPABASE_URL`, `SUPABASE_JWT_SECRET`.
- A Groq API key (free tier, no payment method required — ADR-002) — `GROQ_API_KEY`.
- A Voyage AI API key — `VOYAGE_API_KEY`.
- A GitHub OAuth App or personal access token with `repo` read scope — `GITHUB_TOKEN` (or `GITHUB_CLIENT_ID`/`GITHUB_CLIENT_SECRET` if using OAuth).
- A Notion internal integration token, shared with at least one real page — `NOTION_TOKEN`.
- A small real (or realistic) GitHub repo and a Notion page that follow the deterministic-link convention from `docs/prd.md` §4 (the Notion page contains a link to a real PR/commit in that repo) — needed to exercise User Story 1's primary acceptance scenario.

## Setup

```bash
# backend
cd backend
uv sync
uv run alembic upgrade head    # creates workspace/connector/artifact/relationship/job tables

# frontend
cd ../frontend
pnpm install
```

## Run

```bash
# backend
cd backend
uv run uvicorn src.main:app --reload

# frontend (separate terminal)
cd frontend
pnpm dev
```

## Validation scenarios

Each maps directly to an acceptance scenario in `spec.md`.

### 1. Connect + ingest (User Story 1, Scenario 1)

1. Sign in, `POST /workspaces` to create the one workspace.
2. `POST /connectors/github` with the test repo, then `POST /ingest/{connector_id}`.
3. `POST /connectors/notion` with the test page, then `POST /ingest/{connector_id}`.
4. Poll `GET /connectors/{id}/status` for both until `status: "complete"`.

**Expected**: both reach `complete` without manual DB intervention (SC-001).

### 2. Deterministic citation (User Story 1, Scenario 2)

1. `POST /ask` with a question referencing the Notion page that links to a real PR.

**Expected**: response has `abstained: false`, and `citations` includes the linked PR with `origin: "explicit"` and a working `source_url`.

### 3. No deterministic link (User Story 1, Scenario 3)

1. `POST /ask` about a Notion page with no GitHub link in it.

**Expected**: either a citation with `origin: "inferred"` (never presented as `explicit`), or `abstained: true` — never a confident-looking answer with no real evidence.

### 4. Abstention (User Story 2)

1. `POST /ask` with a question with no plausible connection to any ingested content (e.g. asking about a technology absent from the repo).

**Expected**: `abstained: true`, `citations: []`.

### 5. Citation correctness (User Story 2, zero-tolerance check)

For every response gathered in steps 2-4 above: open each `citations[].source_url` and manually confirm it actually supports the specific claim next to it.

**Expected**: 0 fabricated or unsupported citations across the full run (SC-002). This is the check referenced in the PRD's Phase 1 success bar — run it against at least 10 hand-written questions total, not just the 3-4 above, before calling the feature done.

### 6. Ingestion failure visibility (User Story 3, Scenario 2)

1. Revoke the GitHub token/integration mid-session, trigger `POST /ingest/{connector_id}` again.

**Expected**: `GET /connectors/{id}/status` returns `status: "failed"` (or `needs_reconnect`) with a non-null `error_message` — not a silent hang.

## Out of scope for this validation pass

Per `spec.md` Edge Cases and Assumptions: stale-content detection, incremental sync, and general open-ended repo Q&A with no Notion anchor are not covered here — they're not in Phase 1 scope.
