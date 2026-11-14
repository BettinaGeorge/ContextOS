# ADR-001: Phase 1 MVP technology stack

Status: Accepted, superseded in part by ADR-002 (LLM provider) — locks in real dependencies for Phase 1.

**Superseded note:** the "LLM provider" row below (originally Anthropic Claude) no longer reflects the actual decision — see `docs/decisions/ADR-002-groq-llm-provider.md`. Left in place rather than edited out so this document still shows the reasoning trail (why Claude was chosen first, and why that stopped being valid). Every other row here is still current.

## Context

`docs/prd.md` §4 scopes a Phase 1 MVP: single user, single workspace, single GitHub repo, single Notion source, one workflow, target Friday 2026-07-24. The handoff (§19) suggested a general-purpose stack but explicitly called it "a starting point, not a final decision."

Two constraints shape this decision, and they sometimes pull in different directions:

1. **Budget: total spend must not exceed $10, and should not be recurring.** No paid subscriptions. Metered, pay-per-use costs are acceptable only if they realistically stay well under that cap and there's a way to hard-cap them. (Note: this constraint tightened further after this ADR was first written — see ADR-002 for the LLM-specific consequence.)
2. **Timeline: working by Friday.** Not so tight that every choice has to be the fastest possible one (an earlier draft of this ADR over-indexed on speed at the cost of reliability and cost risk — see the first Alternatives entry below), but real enough that "build it yourself for full control" isn't free either.

Where those constraints conflict, budget wins — a slower or more manual path is preferable to any recurring bill or open-ended cost exposure.

## Decision

| Layer | Choice | Why |
|---|---|---|
| Backend | Python 3.12, FastAPI, Pydantic v2 | Matches builder's existing FastAPI experience (handoff §2); async-friendly for connector calls. Free. |
| ORM / migrations | SQLAlchemy 2.0 + Alembic | Standard, well-documented, works cleanly with pgvector. Free. |
| Primary DB + vector storage | PostgreSQL + pgvector, via **Supabase's free tier** | Free tier covers this project's scale with room to spare. Bundling DB with auth (see below) under one vendor keeps the number of free-tier accounts to track to a minimum. Run locally via Docker during early development; point at the hosted Supabase instance once ready to deploy/share. No dedicated vector DB — pgvector remains correct at this scale regardless of budget, per handoff §19. |
| Graph storage | None — relationships as Postgres rows (per canonical model in PRD §6) | No graph traversal is in scope by Friday (PRD §4); a graph DB would be pure overhead right now, and would also mean a second hosted service to keep free. |
| Background jobs | Postgres-backed job table (a `jobs` row with status/attempts, polled by a worker) — not Redis/Celery/RQ | Needed for real reasons (ingestion status tracking and re-indexing are functional requirements in the PRD, and in-process `BackgroundTasks` loses progress on a restart), but a dedicated queue means hosting Redis somewhere — another free-tier vendor to manage for a service one repo + one Notion source doesn't actually require yet. A DB-backed queue gets the durability without the extra dependency. |
| Auth | **Supabase Auth** (not Clerk) | Free tier is generous (well beyond one user), and since Supabase is already the DB vendor, this avoids adding a second auth-specific vendor (Clerk) with its own free-tier ceiling and billing surface. Trade-off: no prebuilt "Organizations" UI like Clerk's — the workspace/membership model has to be built by hand, which the extended timeline now allows for. |
| Frontend | Next.js (App Router) + TypeScript + React + Tailwind + shadcn/ui, hosted free on **Vercel** | Matches builder's React/TS experience; Vercel's free tier is a genuine $0, no card required for this scale. |
| Backend hosting | **Render free web service tier** | $0. Trade-off: free instances spin down when idle, so first request after inactivity is slow (cold start). Acceptable for a portfolio-stage demo; revisit if this becomes a real UX problem. |
| LLM provider | ~~Anthropic Claude~~ **SUPERSEDED — see ADR-002.** Originally: Anthropic Claude, via a single thin interface, with a hard $8 spend cap. | Assumed a small capped bill was acceptable. It wasn't — actual constraint is $0, no card. ADR-002 records the replacement (Groq) and why. |
| Embeddings | Voyage AI | Also pay-per-use, not a subscription. Code-tuned embedding models (`voyage-code-3`) are a real quality advantage here since the product embeds source code, not just prose — this was a genuine technical fit, not just a fast pick. Cost for embedding one repo + one Notion source is low (one-time ingestion, not per-query), so it fits inside the budget alongside the LLM spend. Reassess toward a free local model (e.g. `sentence-transformers`) if actual usage threatens the $10 cap. |
| Package management | `uv` (backend), `pnpm` (frontend) | Fast installs. Free. |
| Lint/format | `ruff` (backend, lint + format), `eslint` + `prettier` (frontend) | Free. |
| Testing | `pytest` + `pytest-asyncio` (backend), `vitest` + React Testing Library (frontend) | Free. |

**Budget note:** check for the GitHub Student Developer Pack (likely already available) before paying for anything not listed as free above — it doesn't typically cover Anthropic/Voyage usage directly, but may cover incidental needs (domain, extra cloud credit) if free tiers above turn out to be insufficient.

## Consequences

- Multi-repo, multi-tenant collaboration UI, incremental sync, and graph traversal are all still cut for Phase 1, but the data model (workspace_id everywhere, artifact/relationship tables) doesn't block adding them later.
- Building the workspace/membership model by hand (instead of using Clerk's Organizations) is more work than the fastest possible path, but it's a one-time cost paid now in exchange for zero ongoing vendor billing risk.
- The Postgres-backed job table is less capable than a real queue (no built-in retry/backoff, worker concurrency, or dead-letter handling; **superseded in part by ADR-007**, which adds bounded retries with backoff, `FOR UPDATE SKIP LOCKED` claiming and one active job per connector, still without dead-letter handling) — acceptable for one repo + one Notion source; revisit if ingestion volume grows in Phase 2+.
- Render's free-tier cold starts are a real (if minor) UX cost accepted in exchange for $0 hosting.
- LLM spend was originally the one area with genuine (if small and bounded) ongoing cost, mitigated with a hard spend cap rather than eliminated — see ADR-002 for why that stopped being acceptable and what replaced it. Embedding spend (Voyage) is unaffected by that change and still applies.

## Alternatives considered

- **Clerk for auth** — reconsidered and rejected. Originally chosen for speed under the earlier same-weekend timeline; with the budget constraint now explicit, a second billable vendor (even one with a workable free tier) isn't worth it when Supabase Auth covers the same need at $0 with one fewer account to manage.
- **Redis + RQ or Celery for ingestion** — reconsidered and rejected for the same reason: real value (durability, status tracking) but not worth a second hosted free-tier service when a Postgres-backed job table gets most of the benefit at no extra cost.
- **Local-only deployment through Phase 1** — reconsidered and rejected. Originally deferred for speed; now that both Vercel and Render have workable $0 tiers, deploying during Phase 1 costs nothing and better matches wanting to "act like a startup" with something demoable, not just something running on a laptop.
- **Fully local/open-source LLM (via Ollama)** — considered here under the original "$10, not $0" framing and rejected as unnecessary. Revisited in ADR-002 once the constraint became genuinely $0; still rejected there, but for a different, sharper reason (citation-format reliability risk), not because it seemed unnecessary.
- **Full multi-provider LLM abstraction now** — rejected, premature given only one provider is actually used. Still true post-ADR-002 (Groq is that one provider now).
- **Neo4j for relationships** — rejected; no graph traversal is in scope yet, and the handoff itself recommends deferring this.
