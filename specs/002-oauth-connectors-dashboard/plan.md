# Implementation Plan: OAuth Connectors & Project Dashboard

**Branch**: `002-oauth-connectors-dashboard` | **Date**: 2026-07-23 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/002-oauth-connectors-dashboard/spec.md`

## Summary

Replace manual PAT/integration-token entry with provider-hosted authorize-and-pick flows for GitHub and Notion, add Google/GitHub OAuth sign-in alongside the existing magic-link email flow, and turn the signed-in home page into a multi-project dashboard. Technical approach: a **GitHub App** (not a classic OAuth App) for the GitHub connector — its installation screen is GitHub's own native repo picker, and it issues short-lived (1-hour) installation tokens minted on demand from the app's private key rather than one long-lived stored secret; a **Notion public integration** for the Notion connector — its OAuth consent screen is Notion's own native page/database picker, and the resulting access token is long-lived, so it slots into the existing encrypted-token-at-rest storage unchanged. Supabase Auth's built-in Google/GitHub providers handle sign-in as a fully separate concern from connector access (Assumptions, spec.md). The dashboard requires promoting workspace-per-user from an unenforced 1:1 assumption to a real 1:N relationship, which surfaces and fixes a latent bug: `WorkspaceRepository.get_by_owner` uses `scalar_one_or_none()` and would crash today if a user ever owned two workspaces — nothing currently prevents that, `POST /workspaces` has no uniqueness check.

## Technical Context

**Language/Version**: Python 3.12 (backend), TypeScript / Next.js 16, App Router (frontend) — unchanged from feature 001.

**Primary Dependencies (new for this feature)**: `PyJWT` (already a dependency, T054 JWKS work) reused to sign GitHub App JWTs; no new Python package required for GitHub App auth (JWT signing + `httpx`, both already present) or Notion OAuth (`notion-client` already present handles authenticated calls once a token exists; the OAuth code/token exchange itself is a plain `httpx` POST, same pattern as the GitHub connector's existing raw REST calls). Frontend needs no new package — Supabase's existing `@supabase/supabase-js` / `@supabase/ssr` clients already expose `signInWithOAuth`.

**Correction (post-review)**: an earlier draft of this plan listed `GITHUB_APP_CLIENT_ID`/`GITHUB_APP_CLIENT_SECRET` as required new config. Removed — the GitHub App installation flow described in research.md §1 and ADR-003 authenticates entirely via a JWT signed with the App's private key (`GITHUB_APP_ID` + `GITHUB_APP_PRIVATE_KEY`); it never performs a client-id/secret OAuth code exchange. Those two vars would only be needed for a GitHub App's separate user-to-server OAuth flow, which this feature doesn't use (sign-in is a fully separate Supabase-provider flow — Technical Context above, contracts/api.md).

**Storage**: PostgreSQL + pgvector, unchanged. New: `github_app_installation_id` (or equivalent) replaces "encrypted long-lived GitHub token" for GitHub connectors specifically — see data-model.md. Notion connectors keep the existing `encrypted_access_token` column unchanged.

**Testing**: `pytest` + `pytest-asyncio` (backend), `vitest` + React Testing Library (frontend) — unchanged. New: JWT-signing and installation-token-minting logic needs unit coverage with a fake private key (never a real one in tests); OAuth callback handlers need contract tests for the deny/cancel edge cases (spec.md Edge Cases).

**Target Platform**: Web — unchanged (Render backend, Vercel frontend).

**Project Type**: Web application (frontend + backend) — unchanged.

**Performance Goals**: OAuth round-trips add one extra network hop (browser → provider → callback) per connect action versus the old paste-a-token form, but each flow still targets SC-001/SC-002 (repo connected and ingestion started in under 60s of interaction time) — the removed typing time comfortably offsets the added redirect hops.

**Constraints**: $0 for anything requiring a payment method — unchanged from ADR-002, and confirmed still satisfied: registering a GitHub App and a Notion public integration are both free, same as the PAT/internal-integration path they replace. No new external dependency requiring an ADR beyond the two documented below.

**Scale/Scope**: 1 user can now own N workspaces (was 1); each workspace still connects at most one GitHub repo and one Notion source (PRD §4, unchanged by this feature — spec.md Assumptions).

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Check | Result |
|---|---|---|
| I. Evidence-Backed Answers | Not touched by this feature — `answer_svc`'s citation-validation path is unchanged. | PASS (N/A) |
| II. Deterministic Before Inferred | Not touched — relationship extraction is unaffected by how a connector's token was acquired. | PASS (N/A) |
| III. Untrusted Content Boundary | Not touched — ingested content handling is unchanged; only token *acquisition* changes, not what's done with ingested content. | PASS |
| IV. Spec-Driven Development | This plan follows an approved spec (all checklist items pass, one clarification resolved with the user before planning began). | PASS |
| V. Narrowest Credible Scope | Real tension, resolved explicitly rather than silently: multi-workspace-per-user is a genuine scope expansion beyond Phase 1's PRD-locked single-workspace assumption. spec.md FR-007 makes this an explicit, recorded decision (not an incidental addition), and FR-009 explicitly keeps team/sharing out of scope to avoid the expansion snowballing into Phase 6 territory. **Action required**: `docs/prd.md` must be updated to record this scope change in the same change that implements it (constitution's own documentation-update rule), not left to silently diverge. |
| VI. Workspace Isolation | `github_app_installation_id`/Notion OAuth token still live on the `connectors` row, still `workspace_id`-scoped, still routed through the same repositories — isolation model unchanged. | PASS |

**One flagged (not blocking) sequencing note, stated plainly rather than glossed over**: `docs/roadmap.md` treats phase boundaries as real gates, and this feature reaches into territory the roadmap currently splits across Phase 2 (OAuth token acquisition, listed as an open question) and Phase 6 (multi-repo/multi-workspace). Phase 1's own exit criteria (`specs/001-trace-doc-to-code/tasks.md` T061, quickstart scenarios 3–6) were not fully re-run before this feature was spec'd — scenarios 1–2 (the core evidence-backed-answer loop) were validated live against a real repo and passed; scenarios 3, 4, 5, and 6 were not. This was a deliberate, user-directed priority call (build the thing that removes real onboarding friction now), not an oversight — recorded here so it's a visible decision, not a silently skipped gate. Recommend finishing T061's remaining scenarios before `docs/roadmap.md` marks Phase 1 complete, independent of this feature's own progress.

Two new architecture decisions with real trade-offs — **each gets its own ADR before `/speckit-tasks`**, per the constitution's "no new external dependency or service without a new ADR" rule:
- **ADR-003**: GitHub App vs. classic OAuth App for the connector flow.
- **ADR-004**: Notion public integration (OAuth) vs. continuing with internal-integration tokens.

**Post-Phase-1 re-check**: `data-model.md` (the `installation_id`/`encrypted_access_token` mutual-exclusivity constraint), `contracts/api.md` (the `state`-verified callback endpoints, denial paths returning no partial connector), and `research.md` (installation tokens minted on demand rather than stored, `WorkspaceRepository` fix) were reviewed against the table above after being written. No new violations: Principle III (Untrusted Content Boundary) is unaffected since ingested-content handling doesn't change; Principle VI (Workspace Isolation) holds since `installation_id` is still a `workspace_id`-scoped column read through the same repository pattern. Still PASS across all six principles, with the one flagged sequencing note and two required ADRs carried forward as action items into `/speckit-tasks`, not silently dropped.

## Project Structure

### Documentation (this feature)

```text
specs/002-oauth-connectors-dashboard/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/
│   └── api.md           # Phase 1 output — additions/changes to specs/001's contract
└── tasks.md             # Phase 2 output (/speckit-tasks — not yet created)
```

### Source Code (repository root)

```text
backend/
├── src/
│   ├── api/
│   │   ├── auth.py                 # CHANGE: MeResponse drops singular workspace_id
│   │   ├── workspaces.py           # CHANGE: add GET /workspaces (list)
│   │   └── oauth.py                # NEW: /oauth/github/start, /oauth/github/callback,
│   │                                #      /oauth/notion/start, /oauth/notion/callback
│   ├── services/
│   │   ├── connector_svc.py        # CHANGE: GitHub path mints installation tokens
│   │   │                            #         instead of decrypting a stored PAT
│   │   └── oauth_svc.py            # NEW: state-token issuance/verification (CSRF),
│   │                                #      GitHub installation-token minting,
│   │                                #      Notion code-for-token exchange
│   ├── repositories/
│   │   ├── workspace_repository.py # CHANGE: get_by_owner -> list_by_owner
│   │   └── connector_repository.py # CHANGE: GitHub connectors store
│   │                                #         installation_id, not an encrypted PAT
│   ├── connectors/
│   │   └── github_connector.py     # CHANGE: accepts a minted installation token,
│   │                                #         not a decrypted stored one
│   ├── models/
│   │   └── connector.py            # CHANGE: installation_id column (GitHub only)
│   └── core/
│       └── config.py               # NEW: GITHUB_APP_ID, GITHUB_APP_PRIVATE_KEY,
│                                    #      NOTION_OAUTH_CLIENT_ID/SECRET
└── tests/
    ├── unit/
    │   └── test_oauth_svc.py       # NEW
    └── contract/
        └── test_oauth.py           # NEW: deny/cancel edge cases (spec.md Edge Cases)

frontend/
├── src/
│   ├── app/
│   │   ├── page.tsx                # CHANGE: becomes the project dashboard
│   │   ├── projects/new/page.tsx   # NEW: "Add new project" flow entry
│   │   └── connect/page.tsx        # CHANGE: OAuth "Connect" buttons replace
│   │                                #         the token-paste forms
│   └── lib/
│       └── api.ts                  # CHANGE: add listWorkspaces(), OAuth start URLs
└── tests/
```

**Structure Decision**: Extends the existing web application structure from feature 001 — no new top-level directories. The GitHub/Notion connector abstraction (`src/connectors/base.py`) and the encrypted-token repository pattern (`connector_repository.py`) are both reused, not replaced; only the GitHub path's token *shape* changes (short-lived, minted from an installation ID) while Notion's stays a drop-in replacement for the existing encrypted-token flow.

## Complexity Tracking

*No Constitution Check gate failed outright — see the flagged sequencing note and the two required ADRs above. Not a violations table.*
