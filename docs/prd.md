# ContextOS — Product Requirements Document

Status: **Draft v1 — approved for Phase 1 MVP scope.** Source of truth for product scope. Architecture decisions live in `docs/decisions/`. Full original context lives in `CONTEXT_OS_CLAUDE_HANDOFF.md` (background reference, not authoritative where this document differs).

## 1. Decisions locked so far

| Question | Decision | Why |
|---|---|---|
| Audience | Multi-user SaaS, from day one architecturally | Data model is workspace-isolated from the start so this isn't a rewrite later. Functional scope for the Phase 1 MVP still only exercises a single-user path — see §4. |
| First connectors | GitHub + Notion (Jira deferred) | No personal/test Jira access available; Notion is fast to integrate and the builder can generate real test content immediately. Jira is the planned fast-follow connector (see `docs/roadmap.md`) because its structured issue/epic schema is better suited to deterministic relationship extraction long-term. |
| Repo scope | Single repository per workspace | Multi-repo adds cross-repo relationship modeling, retrieval disambiguation, and UI scope that isn't needed to prove the core loop. Data model should not preclude multi-repo later. |
| Timeline | Working MVP by Friday, 2026-07-24, then continuous iteration | Originally targeted "end of weekend" (~1 day); extended to ~6 days once that proved too tight a constraint on its own. Scope in §4 is still cut below the handoff's original MVP definition (§8-9 of the handoff) — the extra days buy room to do the same scope carefully (real tests, a more thorough manual eval pass) rather than an excuse to silently add scope. |
| First persona | Engineer switching teams / joining an existing team | See §2. |
| First workflow | Trace a spec/doc to code | Adapted from "trace a ticket to code" since Notion has no ticket-ID scheme. See §5. |

## 2. Primary persona

**An engineer joining an existing team or switching to an unfamiliar service.** They need to build a working mental model of a codebase and its surrounding context — fast, without waiting on a teammate to walk them through it live.

Why this persona first:
- Matches the builder's own repeated lived experience (most credible to build for and demo).
- The job is bounded and concrete: "understand this thing I don't own yet," not open-ended exploration.
- Naturally forces the product to prove cross-artifact relationship reconstruction, which is the actual differentiator — not just Q&A over one source.

Deferred personas (not designed for yet): engineering managers/leads (need aggregate visibility, not single-question answers — different UI), PMs/designers (need design-artifact connectors not yet built).

## 3. MVP objective

Let a user connect one GitHub repository and one Notion workspace, then ask questions that require connecting a written spec/doc to the code that implements it — and get an answer that cites its sources, distinguishes evidence from inference, and says so when it doesn't have enough evidence.

## 4. MVP scope — target Friday, 2026-07-24 (what ships first)

This is intentionally narrower than the handoff's original MVP section. Anything not listed here is explicitly **out of scope for this build** and lives in `docs/roadmap.md` instead.

**Note (2026-07-23)**: the "one workspace" scoping below was this build's real, intentional Phase 1 boundary — accurate history, not superseded retroactively. It no longer describes the product going forward: `specs/002-oauth-connectors-dashboard/` makes workspace-per-user 1:N (a user can own multiple projects), per §10's now-resolved connector-token-acquisition question.

**In scope:**
- Sign in (single user account, via managed auth — see ADR-001)
- Create one workspace
- Connect one GitHub repository (OAuth or PAT — see ADR-001)
- Connect one Notion workspace/integration, scoped to pages the user selects
- Full (non-incremental) ingestion of: repo files, PRs, commits, issues, contributors from GitHub; pages/blocks from the selected Notion source
- Deterministic relationship extraction only:
  - PR ↔ commit ↔ file (from GitHub metadata directly)
  - Notion doc ↔ PR/commit, via an explicit convention: a GitHub PR/commit link pasted into the Notion doc, or the Notion page URL referenced in a PR/commit description
- Retrieval: keyword (full-text) + vector similarity (pgvector), no graph traversal, no reranking model
- One workflow: **"Trace a spec/doc to code"** (§5)
- Answer generation grounded only in retrieved evidence, with inline source citations (links back to GitHub/Notion), and explicit "insufficient evidence" responses when nothing relevant is found
- Basic error handling for connector auth failures and empty ingestion results

**Explicitly out of scope for this Phase 1 build** (deferred, see roadmap):
- Incremental sync / webhooks
- Multiple repos or multiple Notion sources per workspace
- The other three workflows (understand a feature, fix a bug, explore architecture)
- Model-inferred relationships and confidence scoring
- Graph database or graph traversal retrieval
- Symbol/AST-aware code chunking (start with naive file/function-boundary chunking if time allows, otherwise flat file chunking)
- Team invites / multi-user collaboration UI (data model supports it; UI doesn't need to yet)
- Formal evaluation harness (do a manual spot-check pass against a small hand-written question set instead — see §7)
- Jira or any other connector
- Prompt-injection test suite (basic content sanitization only — see §8)
- Deployment beyond local/dev

## 5. First workflow: "Trace a spec/doc to code"

**User story:** As an engineer new to a codebase, I want to point ContextOS at a Notion doc (a feature spec, design doc, or planning note) and ask "what code implements this?" so I can find the relevant PRs, commits, and files without manually cross-referencing both tools.

**Flow:**
1. User selects a Notion page (or pastes its title/URL) or asks a natural-language question referencing it.
2. ContextOS retrieves the Notion doc content and any deterministically linked GitHub artifacts (via the convention in §4).
3. ContextOS retrieves semantically related code/PRs/commits as a fallback when no deterministic link exists, clearly labeled as inferred, not confirmed.
4. Response includes: synthesized explanation, source citations (doc + PRs/commits/files), and an explicit note when the link is inferred rather than deterministic, or when evidence is insufficient.

**Acceptance criteria** (validated manually against a hand-built set of ~10 question/answer pairs before calling this workflow done):
- Given a Notion doc with an explicit deterministic link to a PR, the system returns that PR with a citation, every time.
- Given a Notion doc with no deterministic link, the system either returns semantically related code labeled as inferred, or explicitly states it found no confident match — it never presents an inferred match as certain.
- No response contains a citation to a source that doesn't actually support the claim next to it (zero tolerance — see `docs/decisions/` for how this gets checked).
- No response fabricates a source URL.

## 6. Data model

Use the canonical artifact/relationship model from the handoff (§12) as-is for this Phase 1 build, scoped to the artifact types actually needed: `source_file`, `commit`, `pull_request`, `issue`, `document` (Notion page). Relationship origins used in this Phase 1 build: `explicit` and `metadata-derived` only — `model-inferred` and `user-confirmed` are schema-ready but not exercised yet.

## 7. Success criteria

**Phase 1 MVP (functional bar, not a benchmark):**
- A cold-start user can sign in, connect GitHub + Notion, select a repo, and get one grounded, cited answer to a real question — start to finish, no manual DB intervention.
- Zero fabricated citations across a manually-run set of ~10 test questions.
- At least 7 of 10 hand-written test questions get a genuinely useful, correctly-cited answer (the other 3 may legitimately abstain if evidence really is missing — that counts as correct behavior, not failure).

**Near-term (once eval harness exists — Phase 3 of the roadmap):**
- Citation correctness ≥ 95% against a labeled eval set
- Recall@10 for exact-ID/exact-filename queries measured and tracked (no target yet — first pass establishes the baseline)
- Time-to-context: self-timed comparison of "trace a doc to code" via ContextOS vs. manually cross-referencing GitHub + Notion, on the same ~10 questions

## 8. Non-functional requirements (Phase 1 scope)

- Connector tokens encrypted at rest, never logged in plaintext
- All ingested content (repo files, commit messages, PR descriptions, Notion page content) treated as untrusted input — never interpreted as instructions to the model (basic system-prompt/content separation; full adversarial test suite deferred to Phase 3)
- Data isolated by `workspace_id` on every table, even though only one workspace is exercised by Friday (2026-07-24)
- No training on ingested content

## 9. Non-goals (current)

Carried over from the handoff (§21), still valid:
- Every connector — only GitHub + Notion now, Jira next
- Full enterprise permission-sync engine
- Real-time ingestion for every platform
- IDE extension
- Autonomous code modification or deployment
- General-purpose enterprise assistant
- Replacement for GitHub/Jira/Figma/Slack themselves
- Perfect multi-language repository understanding
- Fully autonomous incident response
- Polished billing system

## 10. Open questions (explicitly deferred, not silently decided)

- Exact chunking strategy for code (naive vs. function-boundary) — decide during implementation if time allows by Friday (2026-07-24); default to naive if not.
- Whether Notion's own API rate limits or block-nesting model cause meaningful ingestion friction — unknown until integration is attempted.
- Real thresholds for the near-term success metrics in §7 — can't be set responsibly before the eval harness exists.
- ~~**Connector token acquisition: manual PAT/integration-token paste (current) vs. Supabase OAuth providers (GitHub, Notion) using `session.provider_token`.**~~ **RESOLVED 2026-07-23** — revisited once Phase 1's core loop was validated live against a real repo, exactly as this entry anticipated. Decided *against* the `session.provider_token` approach this entry originally sketched (confirmed unusable: Supabase doesn't persist it past the callback moment) in favor of two dedicated OAuth mechanisms: a **GitHub App** for repo access (`docs/decisions/ADR-003-github-app-connector.md`) and a **Notion public integration** (`docs/decisions/ADR-004-notion-public-integration.md`). Full scope, including the accompanying multi-workspace-per-user change this unlocks, is specified in `specs/002-oauth-connectors-dashboard/`.
