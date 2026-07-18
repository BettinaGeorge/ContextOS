# ContextOS — Roadmap

Phased against the scope decisions in `docs/prd.md`. Each phase should be functionally shippable before the next begins — no phase starts until the previous one's acceptance criteria are met.

## Phase 0 — Product definition (done)

- Restated product understanding, resolved open questions from the handoff
- Locked: audience (multi-tenant-ready architecture), first connectors (GitHub + Notion), repo scope (single), first persona, first workflow
- Wrote `docs/vision.md`, `docs/prd.md`, this roadmap

## Phase 1 — Phase 1 MVP

Scope defined in `docs/prd.md` §4. Target: Friday, 2026-07-24.

- Auth + single workspace creation
- GitHub connector: OAuth/PAT, single repo, full ingestion (files, PRs, commits, issues)
- Notion connector: single workspace/integration, full ingestion of selected pages
- Common artifact model (`explicit` + `metadata-derived` relationships only)
- Retrieval: full-text + vector (pgvector), no graph traversal yet
- "Trace a spec/doc to code" workflow, end to end
- Citations on every answer; explicit abstention when evidence is insufficient
- Manual validation against the ~10-question set in `docs/prd.md` §7

**Exit criteria:** success criteria in PRD §7 (Phase 1 bar) are met.

## Phase 2 — Harden the core loop

- Incremental sync for GitHub and Notion (webhooks or polling)
- Improve code chunking (move from naive to function/class-boundary if not done in Phase 1)
- Expand the deterministic-relationship convention if manual testing in Phase 1 revealed gaps
- Basic ingestion error handling and retry behavior
- Real deployment (not local-only) — Railway/Render/Fly per ADR-001, managed Postgres

## Phase 3 — Reliability pass

Per the handoff's principle that reliability is a product requirement, not a later polish step:

- Build the formal evaluation harness against the question set started in Phase 1 (expand it)
- Citation validation (automated check that a cited source actually supports the claim next to it)
- Conflict detection between sources
- Prompt-injection adversarial test suite (content from repo/Notion treated as untrusted input, tested against actual injection attempts)
- Retrieval + generation tracing/observability

**Do not add new workflows or connectors before this phase is done.** Breadth before reliability is exactly the failure mode this project is designed to avoid.

## Phase 4 — Jira connector (fast-follow)

- Jira OAuth, issue/epic/comment ingestion
- Deterministic relationship extraction via ticket IDs in branch names/PR titles/commits — the structured linking Notion couldn't offer
- Re-evaluate whether "trace a ticket to code" should become the primary workflow once real Jira data exists

## Phase 5 — Additional workflows

Using the now-hardened retrieval stack:
- "Understand a feature"
- "Explore repository architecture"
- Introduce semantic + graph-aware retrieval (relationship traversal beyond direct/deterministic links) if the simpler retrieval from Phase 1-2 is proving insufficient

## Phase 6 — Third connector + multi-repo / multi-user

- Multi-repo support per workspace
- Real team/invite UI (data model has supported this since Phase 1; build the functional surface now)
- Third connector — Figma is the most compelling per the original handoff (introduces multimodal, design-to-code context), Slack/Linear are alternatives

## Phase 7 — Proactive intelligence

- Stale documentation detection
- Unimplemented-requirement detection
- Change-impact summaries
- Onboarding-path generation

---

Each phase should get its own `specs/NNN-<name>/spec.md` + `plan.md` + `tasks.md` before implementation starts, per the spec-driven workflow in `CLAUDE.md`.
