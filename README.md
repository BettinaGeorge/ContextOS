# ContextOS

AI-native context engine that connects GitHub, Jira, Notion, and other engineering tools to give evidence-backed answers about how code, requirements, and decisions relate.

Every answer ContextOS gives is grounded in retrieved evidence — it cites its sources, labels inference separately from fact, and says so explicitly when it doesn't have enough evidence to answer responsibly. See [`docs/vision.md`](docs/vision.md) for the full pitch and origin story.

## Status

**Phase 1 MVP in progress** (target: Friday, 2026-07-24). Currently ships: sign-in, one workspace, one connected GitHub repo, one connected Notion source, and a single workflow — **"trace a spec/doc to code."** See [`docs/roadmap.md`](docs/roadmap.md) for what's next.

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
|                       Next.js 15 . TypeScript . Vercel                       |
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
|                          FastAPI . Python . Render                           |
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
|  |               |  | github, notion |  | jobs table:   |  | fulltext +    | |
|  |               |  |                |  | poll, retry   |  | vector        | |
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
|  | OAuth/PAT auth                 |  | Notion integration token       |      |
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

`backend/` and `frontend/` don't exist in this repo yet — this diagram describes the target Phase 1 architecture that [`specs/001-trace-doc-to-code/`](specs/001-trace-doc-to-code/) is being built against, not code that's already running.
