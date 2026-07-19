# ContextOS Constitution

## Core Principles

### I. Evidence-Backed Answers (NON-NEGOTIABLE)
Every factual claim in a generated response must be traceable to a retrieved source. Citations must be validated against what was actually retrieved before being returned — never let generation assert a source that wasn't in the evidence packet. When evidence is insufficient, the system must say so explicitly rather than guess. Zero tolerance for fabricated citations.

### II. Deterministic Before Inferred
Relationship extraction between artifacts (doc ↔ PR, ticket ↔ commit, etc.) must prefer explicit, deterministic signals (IDs, links, metadata) over model inference. Model-inferred relationships are permitted only when no deterministic signal exists, and must always be labeled as inferred, never presented with the same confidence as a deterministic link.

### III. Untrusted Content Boundary
All ingested content — repository files, commit messages, PR descriptions, Notion page content, and any future connector's content — is untrusted input, not instructions. System prompts and retrieved content must remain strictly separated. No ingested content may alter model behavior, and no code from ingested artifacts is ever executed.

### IV. Spec-Driven Development
No implementation code is written before an approved spec with testable acceptance criteria exists. Required sequence: requirement → specification → acceptance criteria → architecture decision → implementation plan → tasks → code → tests → validation → documentation update. Ambiguous requirements are clarified before planning, not resolved by silent assumption during implementation.

### V. Narrowest Credible Scope
No feature, abstraction, connector, or generalization is built ahead of proven need. The current MVP scope (single repo, single Notion source, one workflow, deterministic relationships only) is a deliberate constraint, not a placeholder to casually expand. Scope changes are explicit decisions recorded in `docs/prd.md`, not incidental additions during implementation.

### VI. Workspace Isolation
Every artifact and relationship is scoped by `workspace_id`, even while only one workspace exists. No query or data access path may assume single-tenancy "because there's only one workspace right now."

## Technology Constraints

Stack is fixed per `docs/decisions/ADR-001-weekend-mvp-stack.md` and `ADR-002-groq-llm-provider.md`: Python/FastAPI/SQLAlchemy/Postgres+pgvector backend (hosted free on Supabase), Next.js/TypeScript frontend (hosted free on Vercel), Supabase Auth, Groq (single-provider interface, not a multi-provider abstraction) for generation, Voyage AI for embeddings. Budget constraint: $0 for anything requiring a payment method (tightened from an earlier "$10 cap" once a capped-but-real bill turned out not to be acceptable — see ADR-002). No new external dependency or service is introduced without a new ADR under `docs/decisions/` documenting both the trade-off and its cost.

## Development Workflow

- Every feature gets a `specs/NNN-<feature-name>/` folder (`spec.md`, `plan.md`, `tasks.md`) before code is written, per the Spec Kit workflow (`/speckit-specify` → `/speckit-plan` → `/speckit-tasks` → `/speckit-implement`).
- `docs/roadmap.md` phase boundaries are real gates — do not begin Phase N+1 work while Phase N's exit criteria are unmet.
- Documentation (`docs/prd.md`, `docs/roadmap.md`, relevant ADRs) is updated in the same change that alters the decisions they describe. Docs and code must never be allowed to silently diverge.
- `CLAUDE.md` carries the day-to-day operational conventions (repo structure, commands, security rules); this constitution carries the non-negotiable principles those conventions must never violate. If the two ever conflict, this constitution wins and `CLAUDE.md` must be corrected.

## Governance

This constitution supersedes ad hoc practice. Amendments require: a documented reason, an update to this file, and a check that `CLAUDE.md` and `docs/prd.md` remain consistent with the change. Complexity beyond what a principle above allows must be justified in writing (an ADR) before it's implemented, not after.

**Version**: 1.0.0 | **Ratified**: 2026-07-18 | **Last Amended**: 2026-07-18
