# ContextOS

AI-native context engine that connects GitHub and Notion (Jira and others planned) to give evidence-backed answers about how code, requirements, and decisions relate.

Every answer ContextOS gives is grounded in retrieved evidence — it cites its sources, labels inference separately from fact, and says so explicitly when it doesn't have enough evidence to answer responsibly. See [`docs/vision.md`](docs/vision.md) for the full pitch and origin story.

## Status

**Phase 1 MVP is implemented and runs locally; the final manual validation pass is still open** (task T061 in [`specs/001-trace-doc-to-code/tasks.md`](specs/001-trace-doc-to-code/tasks.md)). Last commit: 2026-07-26.

Implemented in code:

- Sign-in (Supabase email magic link) and one workspace
- One GitHub repo (connected with an access token) and one Notion source (integration token), ingested in full
- One workflow: **"trace a spec/doc to code"**
- Retrieval over keyword and vector search, with answers that cite only evidence the service itself retrieved, and that abstain when the evidence is insufficient
- Backend tests (pytest, 57 test functions) and a small frontend test suite (vitest, 2 tests)

Not done yet:

- Manual validation against the PRD's ~10-question set (T061)
- Hosted deployment (Vercel + Render are the planned targets, see [ADR-001](docs/decisions/ADR-001-weekend-mvp-stack.md); [`docs/roadmap.md`](docs/roadmap.md) lists real deployment under Phase 2)
- OAuth connect flow and dashboard: specified and planned in [`specs/002-oauth-connectors-dashboard/`](specs/002-oauth-connectors-dashboard/), no tasks started
- Jira connector, incremental sync, and an automated evaluation harness (roadmap Phases 2–4)

See [`docs/roadmap.md`](docs/roadmap.md) for the full plan.

## How an answer is produced

1. The question arrives at `POST /ask`, optionally with a Notion doc URL.
2. If a doc URL is given, the service loads that doc and the artifacts it is explicitly linked to (a PR or commit URL in the doc, or the doc URL in a PR or commit description). These are labeled `explicit` or `metadata-derived`.
3. Retrieval adds more candidates: a keyword match plus pgvector cosine similarity over Voyage `voyage-code-3` embeddings. These are labeled `inferred`.
4. Groq (Llama 3.3 70B) answers from an `<evidence>` block in the user turn. The system prompt is a fixed constant and never contains retrieved content.
5. The service keeps only citations whose artifact IDs it actually retrieved. If none remain, or the model reports insufficient evidence, the answer is an abstention.

Code is chunked on function and class boundaries (Python via the standard-library `ast`, heuristic boundaries for TypeScript/JavaScript, fixed-size line windows otherwise).

## Known limitations

- Keyword search is a case-insensitive substring match (`ILIKE`), not Postgres full-text search, and keyword and vector results are concatenated rather than score-merged.
- Ingestion jobs run from a Postgres table polled by an in-process worker. There is no retry or backoff, and the job-claim step is only safe with a single worker. [ADR-001](docs/decisions/ADR-001-weekend-mvp-stack.md) accepts this for Phase 1.
- Prompt-injection defense is structural (prompt separation plus citation validation). Adversarial testing against the live model is planned for roadmap Phase 3.
- Re-ingestion is always full; there is no incremental sync.
- Source-system permissions are not synced.

## Docs

| Doc | What's in it |
|---|---|
| [`docs/vision.md`](docs/vision.md) | Product vision, differentiation, origin story |
| [`docs/prd.md`](docs/prd.md) | Locked product decisions, persona, MVP scope, success criteria |
| [`docs/roadmap.md`](docs/roadmap.md) | Phased plan, Phase 1 → Phase 7 |
| [`docs/decisions/`](docs/decisions/) | Architecture decision records (ADRs) |
| [`.specify/memory/constitution.md`](.specify/memory/constitution.md) | Non-negotiable engineering principles |
| [`CLAUDE.md`](CLAUDE.md) | Agent/contributor operating conventions |
| [`specs/`](specs/) | Per-feature specs, plans, and tasks (spec-driven development via [GitHub Spec Kit](https://github.com/github/spec-kit)) |

## Architecture

```
                      CONTEXTOS  --  System Architecture

+------------------------------------------------------------------------------+
|                             USER INTERFACE LAYER                             |
|                Next.js 16 . TypeScript . (Vercel planned)                    |
|                                                                              |
|                                                                              |
|  +--------------+  +--------------+  +--------------+  +--------------+      |
|  | Workspace    |  | Connectors   |  | Ask          |  | Ingestion    |      |
|  | /            |  | /connect     |  | /ask         |  | /status      |      |
|  | sign in,     |  | GitHub,      |  | trace doc    |  | progress,    |      |
|  | create       |  | Notion       |  | -> code      |  | errors       |      |
|  +--------------+  +--------------+  +--------------+  +--------------+      |
|                                                                              |
|                       lib/api.ts -- typed REST client                        |
+------------------------------------------------------------------------------+
                                      |
                               REST API / HTTPS
                                      |
                                      v
+------------------------------------------------------------------------------+
|                              BACKEND API LAYER                               |
|                    FastAPI . Python . (Render planned)                       |
|                                                                              |
|                                 CONTROLLERS                                  |
|                                                                              |
|  +----------------+  +----------------+  +----------------+                  |
|  | /auth/*        |  | /workspaces/*  |  | /connectors/*  |                  |
|  | session via    |  | POST create    |  | POST github    |                  |
|  | Supabase Auth  |  | GET get        |  | POST notion    |                  |
|  |                |  |                |  | GET status     |                  |
|  +----------------+  +----------------+  +----------------+                  |
|                                                                              |
|  +----------------+  +------------------+                                    |
|  | /ingest/*      |  | /ask             |                                    |
|  | POST trigger   |  | POST question    |                                    |
|  | GET status     |  | -> cited answer  |                                    |
|  +----------------+  +------------------+                                    |
|                                                                              |
|                                   SERVICES                                   |
|                                                                              |
|  +---------------+  +----------------+  +---------------+  +---------------+ |
|  | workspace_svc |  | connector_svc  |  | ingestion_svc |  | retrieval_svc | |
|  |               |  | github, notion |  | jobs table:   |  | keyword +     | |
|  |               |  |                |  | poll          |  | vector        | |
|  +---------------+  +----------------+  +---------------+  +---------------+ |
|                                                                              |
|  +-----------------+  +-------------------+                                  |
|  | answer_svc      |  | relationship_svc  |                                  |
|  | citation val.,  |  | deterministic     |                                  |
|  | abstain logic   |  | link extraction   |                                  |
|  +-----------------+  +-------------------+                                  |
|                                                                              |
|                                 REPOSITORIES                                 |
|                                                                              |
|  +----------------------+  +--------------------------+  +-----------------+ |
|  | artifact_repository  |  | relationship_repository  |  | job_repository  | |
|  | CRUD, filter         |  | create, query            |  | enqueue, poll   | |
|  +----------------------+  +--------------------------+  +-----------------+ |
+------------------------------------------------------------------------------+

  +-----------------------+  +-----------------------+  +-----------------------+  +----------------+
  | PostgreSQL + pgvector |  | Groq (Llama 3.3 70B)  |  | Voyage AI             |  | Supabase Auth  |
  | Supabase (free tier)  |  | single-provider       |  | voyage-code-3         |  |                |
  |                       |  | interface, free tier  |  | (code-tuned)          |  |                |
  | workspaces            |  |                       |  |                       |  |                |
  | artifacts             |  | grounded generation   |  | embeds source_file /  |  | users          |
  | relationships         |  | + citation            |  | PR / commit / doc     |  | workspace      |
  | jobs (queue table)    |  | validation            |  | chunks                |  | membership     |
  +-----------------------+  +-----------------------+  +-----------------------+  +----------------+
     SQLAlchemy ORM             Groq SDK             Voyage SDK       Supabase SDK

+------------------------------------------------------------------------------+
|                INGESTION LAYER . Connector Interface Pattern                 |
|                                                                              |
|                                                                              |
|  +--------------------------------+  +--------------------------------+      |
|  | GitHubConnector  [done] Phase 1 |  | NotionConnector  [done] Phase 1 |    |
|  |                                |  |                                |      |
|  | access token (PAT)             |  | Notion integration token       |      |
|  | ingest_full(): files, PRs,     |  | ingest_full(): selected        |      |
|  | commits, issues, contributors  |  | pages / blocks                 |      |
|  | normalize_artifact()           |  | normalize_artifact()           |      |
|  |                                |  | deterministic link: PR/commit  |      |
|  |                                |  | URL in doc, or doc URL in      |      |
|  |                                |  | PR/commit description          |      |
|  +--------------------------------+  +--------------------------------+      |
|                                                                              |
|  +--------------------------------+                                          |
|  | JiraConnector  [ ] planned     |                                          |
|  |                                |                                          |
|  | blocked: no personal Jira      |                                          |
|  | access yet. Deferred to        |                                          |
|  | Phase 4 (docs/roadmap.md)      |                                          |
|  +--------------------------------+                                          |
|                                                                              |
|  Common interface (CONTEXT_OS_CLAUDE_HANDOFF.md §11):                        |
|  authenticate() . ingest_full() . normalize_artifact() .                     |
|  normalize_relationship() . health_check()                                   |
+------------------------------------------------------------------------------+
```

Every box above traces back to an explicit decision, not a default: see [`docs/decisions/ADR-001-weekend-mvp-stack.md`](docs/decisions/ADR-001-weekend-mvp-stack.md) and [`ADR-002-groq-llm-provider.md`](docs/decisions/ADR-002-groq-llm-provider.md) for why (budget-constrained: $0 for anything requiring a payment method). Generation (Groq) is confirmed free-tier, no card. Embeddings (Voyage AI) is still pay-per-use as originally chosen in ADR-001 — not yet revisited under the tightened $0 constraint; a free/local embeddings alternative is still an open question.

The code lives in [`backend/`](backend/) (FastAPI) and [`frontend/`](frontend/) (Next.js). The diagram shows the Phase 1 architecture from [`specs/001-trace-doc-to-code/`](specs/001-trace-doc-to-code/); the Vercel and Render boxes are deployment targets, not live hosts. To run it locally, see the Commands section of [`CLAUDE.md`](CLAUDE.md) and [`specs/001-trace-doc-to-code/quickstart.md`](specs/001-trace-doc-to-code/quickstart.md).
