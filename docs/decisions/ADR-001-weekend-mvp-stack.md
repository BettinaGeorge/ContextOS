# ADR-001: Weekend MVP technology stack

Status: Proposed — flagging for confirmation before implementation starts, since this locks in real dependencies.

## Context

`docs/prd.md` §4 scopes a Weekend MVP: single user, single workspace, single GitHub repo, single Notion source, one workflow. The handoff (§19) suggested a general-purpose stack but explicitly called it "a starting point, not a final decision." We need a concrete, minimal choice now because CLAUDE.md needs real commands, and because indecision here is itself a time cost against the weekend deadline.

Guiding constraint: pick the stack that gets a working, demoable product by Sunday — not the stack that's most "correct" for a mature multi-tenant SaaS. Anything that isn't needed to hit the Weekend MVP acceptance criteria is deferred, even if the handoff mentions it.

## Decision

| Layer | Choice | Why |
|---|---|---|
| Backend | Python 3.12, FastAPI, Pydantic v2 | Matches builder's existing FastAPI experience (handoff §2); async-friendly for connector calls. |
| ORM / migrations | SQLAlchemy 2.0 + Alembic | Standard, well-documented, works cleanly with pgvector. |
| Primary DB | PostgreSQL | Per handoff §19. |
| Vector storage | pgvector extension on the same Postgres instance | Per handoff §19 — avoid a second database for the weekend. |
| Graph storage | None — relationships as Postgres rows (per canonical model in PRD §6) | No graph traversal is in scope this weekend (PRD §4); a graph DB would be pure overhead right now. |
| Background jobs | None — synchronous ingestion or FastAPI `BackgroundTasks` | Ingesting one repo + one Notion source is small enough not to need Celery/Redis. Revisit in Phase 2 if ingestion time becomes a UX problem. |
| Auth | Managed provider (Clerk) rather than hand-rolled | Building auth from scratch this weekend would eat the majority of the available time. Clerk has native org/workspace support, which keeps the multi-tenant-ready data model intent from PRD §1 without hand-building it. |
| Frontend | Next.js (App Router) + TypeScript + React + Tailwind + shadcn/ui | Matches builder's React/TS experience; shadcn/ui per handoff §19. |
| LLM provider | Anthropic Claude, via a single thin interface (not a multi-provider abstraction) | Multi-provider abstraction before there's one working provider is premature (development principle #1, no overengineering). Interface is still isolated behind one module so swapping later isn't a rewrite. |
| Embeddings | Voyage AI | Hosted, no local model management, commonly paired with Claude. Reassess if cost/quota becomes an issue. |
| Package management | `uv` (backend), `pnpm` (frontend) | Fast installs, matters when iterating quickly over a weekend. |
| Lint/format | `ruff` (backend, lint + format), `eslint` + `prettier` (frontend) | |
| Testing | `pytest` + `pytest-asyncio` (backend), `vitest` + React Testing Library (frontend) | |
| Deployment | Local/dev only this weekend | Real deployment is Phase 2 (`docs/roadmap.md`) — not needed to validate the workflow. |

## Consequences

- Multi-repo, multi-tenant collaboration UI, incremental sync, graph traversal, and a job queue are all cut for the weekend but the data model (workspace_id everywhere, artifact/relationship tables) doesn't block adding them later.
- Depending on a managed auth provider (Clerk) is a real external dependency and a cost consideration once past free tier — acceptable trade for weekend velocity, but worth revisiting if the project grows.
- No graph database avoids premature complexity per the handoff's own guidance (§19: "avoid introducing a graph database too early unless benchmarks show it is needed").

## Alternatives considered

- **Full multi-provider LLM abstraction now** — rejected, premature given only one provider is actually used.
- **Celery + Redis for ingestion** — rejected for the weekend; one repo + one Notion source doesn't need a distributed queue yet.
- **Hand-rolled auth** — rejected for the weekend; not the differentiated part of the product, not worth the time this weekend.
- **Neo4j for relationships** — rejected; no graph traversal is in scope yet, and the handoff itself recommends deferring this.
