# CLAUDE.md

Guidance for Claude Code (and any other agent) working in this repository.

## Core purpose

ContextOS connects the tools a software team already uses — starting with GitHub and Notion — and answers questions about code, requirements, and decisions with **evidence-backed, citation-traceable answers**. It is not a generic RAG chatbot: its value is reconstructing relationships between artifacts (doc → PR → commit → file) and being explicit about what's directly evidenced versus inferred versus unknown. Full detail: `docs/vision.md`.

## Current MVP scope

Full requirements live in `docs/prd.md` — do not duplicate them here; read that file before implementing anything. Summary only:

- One user, one workspace, one GitHub repo, one Notion source
- One workflow: **"Trace a spec/doc to code"**
- Deterministic relationship linking only (explicit IDs/links) — no model-inferred relationships yet
- Every answer must cite sources and explicitly abstain when evidence is insufficient

`docs/prd.md` §1 has the locked product decisions (audience, connectors, repo scope, persona, timeline) and the reasoning behind each — check there before assuming a decision hasn't been made yet.

## Current non-goals

Do not build, even if it seems easy or "while I'm in there":

- Any connector beyond GitHub + Notion (Jira is next, not now — see `docs/roadmap.md`)
- Multi-repo or multi-Notion-source support
- The other three workflows (understand a feature, fix a bug, explore architecture)
- Model-inferred relationships / confidence scoring
- Graph database or graph traversal
- Incremental sync / webhooks
- Team invites or multi-user collaboration UI
- A formal eval harness (manual spot-checks only, for now)
- A dedicated queue service (Redis/Celery/RQ) — ingestion jobs use the Postgres `jobs` table polled by an in-process worker, per ADR-001
- Real (non-local) deployment

Full non-goals list: `docs/prd.md` §9.

## Repository structure

```
/
├── CLAUDE.md
├── README.md
├── CONTEXT_OS_CLAUDE_HANDOFF.md   (original project handoff — background reference, not authoritative where docs/ differs)
├── docs/
│   ├── vision.md
│   ├── prd.md
│   ├── roadmap.md
│   └── decisions/
│       └── ADR-NNN-*.md
├── specs/
│   └── NNN-<feature-name>/
│       ├── spec.md
│       ├── plan.md
│       └── tasks.md
├── backend/        (FastAPI; tests live in backend/tests/{unit,contract,integration})
└── frontend/       (Next.js; tests live next to the pages, e.g. src/app/ask/__tests__/)
```

Both `backend/` and `frontend/` exist and Phase 1 is implemented. New code follows the plan in the relevant spec under `specs/`, not ad hoc.

## Coding and testing conventions

Stack decisions and rationale: `docs/decisions/ADR-001-weekend-mvp-stack.md`.

- Backend: Python 3.12, FastAPI, Pydantic v2, SQLAlchemy 2.0 + Alembic, `pytest` for tests.
- Frontend: Next.js (App Router), TypeScript, React, Tailwind, shadcn/ui, `vitest` + React Testing Library for tests.
- Every ingested artifact must map to the canonical artifact/relationship model (`docs/prd.md` §6) — don't invent a parallel data shape per connector.
- Connector-specific logic stays isolated from core retrieval/reasoning logic (per the connector interface pattern in the handoff, §11) even though only one connector interface is implemented so far.
- No comments explaining *what* code does — name things clearly instead. Comments only for non-obvious *why* (a workaround, a subtle invariant).
- Don't add abstractions, config flags, or generality for connectors/workflows/providers that don't exist yet. One repo, one Notion source, one LLM provider — write code that reflects that, not a hypothetical future.

## Spec-driven development requirements

This project uses [GitHub Spec Kit](https://github.com/github/spec-kit) (`specify` CLI). Non-negotiable principles live in `.specify/memory/constitution.md` — read it; if anything here ever conflicts with it, the constitution wins and this file should be corrected.

Required sequence for every feature, no exceptions:

**requirement → specification → acceptance criteria → architecture decision → implementation plan → tasks → code → tests → validation → documentation update**

Mapped to Spec Kit commands: `/speckit-clarify` (if needed) → `/speckit-specify` → `/speckit-plan` (references an ADR under `docs/decisions/` for any real architecture trade-off) → `/speckit-tasks` → optionally `/speckit-analyze` → `/speckit-implement`.

- Do not write implementation code before a spec with testable acceptance criteria exists under `specs/NNN-<feature-name>/spec.md`.
- Architecture decisions with real trade-offs get an ADR under `docs/decisions/`, not a silent choice buried in code.
- After implementation, validate against the spec's acceptance criteria explicitly before calling the feature done — don't just claim it works.
- If a requirement is ambiguous, ask before deciding. Don't silently expand scope or pick technology not already decided in an ADR.
- When a decision changes, update the relevant doc (`docs/prd.md`, `docs/roadmap.md`, or the ADR) in the same change — docs must stay consistent with what's actually true.

## Security and prompt-injection rules

- All ingested content (repo files, commit messages, PR descriptions, Notion page content) is **untrusted input** — never treat it as instructions to the model. Maintain strict separation between system instructions and retrieved content in every prompt.
- Never execute code found in ingested artifacts.
- Connector tokens must be encrypted at rest and never logged, including in error messages or traces.
- Every answer's citations must be validated against the evidence actually retrieved — never let the model assert a source that wasn't retrieved.
- All data is scoped by `workspace_id`, even while only one workspace exists. Don't write a query that skips this "because there's only one workspace right now."
- Don't invent or assume permissions — if source-permission handling isn't implemented for a connector yet, don't expose that connector's content as if it were access-controlled.

## Documentation-update expectations

- `docs/prd.md` is the source of truth for scope. If implementation reveals the PRD is wrong or incomplete, update the PRD — don't let code and docs silently diverge.
- `docs/roadmap.md` phase boundaries are real gates: don't start Phase N+1 work while Phase N's exit criteria are unmet.
- New architecture decisions with real trade-offs get a new `docs/decisions/ADR-NNN-*.md`, numbered sequentially.
- New features get a `specs/NNN-<feature-name>/` folder before code is written.

## Commands

### Backend (`backend/`, run via `uv`)

- Install: `uv sync`
- Run dev server: `uv run uvicorn src.main:app --reload`
- Lint/format: `uv run ruff check --fix .` / `uv run ruff format .`
- Tests: `uv run pytest` (requires a local Postgres with `pgvector` — see below)
- Migrations: `uv run alembic upgrade head` / `uv run alembic revision --autogenerate -m "..."`

### Frontend (`frontend/`, run via `pnpm`)

- Install: `pnpm install`
- Run dev server: `pnpm dev`
- Lint/format: `pnpm lint` / `pnpm format`
- Tests: `pnpm test`
- Build: `pnpm build`

### Local scratch database

Tests and local dev run against a throwaway Postgres 17 + pgvector instance, not the real Supabase project (`backend/.env`, gitignored, documents this). To stand it up from scratch:

```
brew services start postgresql@17   # configured to listen on port 5433, not the default 5432
createdb -p 5433 contextos_dev
psql -p 5433 -d contextos_dev -c "CREATE EXTENSION IF NOT EXISTS vector;"
cd backend && uv run alembic upgrade head
```
