# Tasks: OAuth Connectors & Project Dashboard

**Input**: Design documents from `/specs/002-oauth-connectors-dashboard/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/api.md, quickstart.md — all present. ADR-003 and ADR-004 ratified (referenced from `.specify/memory/constitution.md`'s Technology Constraints).

**Tests**: Included, same standard as feature 001 (constitution's `code → tests → validation` sequence, CLAUDE.md conventions) — not a default being overridden without reason.

**Organization**: Tasks are grouped by user story (spec.md) so each is independently implementable, testable, and demoable. Story priority order: US1 (GitHub OAuth) → US2 (Notion OAuth) → US3 (Dashboard) → US4 (Social sign-in).

**Scope note carried from plan.md**: the Constitution Check flagged that feature 001's quickstart scenarios 3–6 were not fully re-run before this feature was spec'd (a deliberate, user-directed priority call, not an oversight). Not this feature's job to backfill — noted here so it isn't silently forgotten, matching how plan.md already surfaced it.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependency on an incomplete task)
- **[Story]**: Maps to spec.md's US1/US2/US3/US4
- Paths follow the Web application structure from plan.md (`backend/src/`, `frontend/src/`)

---

## Phase 1: Setup

- [ ] T001 Register a GitHub App (research.md §1) — App ID, generated private key, installation URL; add `GITHUB_APP_ID`, `GITHUB_APP_PRIVATE_KEY` to `.env.example` and local `backend/.env` (account/dashboard setup, not code — same category as Phase 1's Supabase/Groq/Voyage account setup). No client ID/secret needed — the installation flow authenticates via JWT + private key only (research.md §1, ADR-003), not a code exchange.
- [ ] T002 Convert the existing Phase 1 Notion internal integration to a **public** integration, or register a new one (research.md §2) — client ID, client secret, redirect URI; add `NOTION_OAUTH_CLIENT_ID`, `NOTION_OAUTH_CLIENT_SECRET` to `.env.example` and local `backend/.env`
- [ ] T003 Enable Google and GitHub sign-in providers in the Supabase project's Authentication → Providers settings (account/dashboard configuration, not code — quickstart.md Prerequisites)
- [ ] T004 [P] Add the four new settings fields (`github_app_id`, `github_app_private_key`, `notion_oauth_client_id`, `notion_oauth_client_secret`) to `Settings` in `backend/src/core/config.py`
- [ ] T005 [P] Add a signing secret for OAuth `state` tokens (research.md §5) — reuse `token_encryption_key` or add a dedicated `state_signing_key` field to `backend/src/core/config.py`; document the choice in a one-line comment since it's a judgment call not made in research.md

---

## Phase 2: Foundational (Blocking Prerequisites)

**⚠️ CRITICAL**: No user story work begins until this phase is complete.

- [ ] T006 Add DB migration: make `connectors.encrypted_access_token` nullable, add `connectors.installation_id` (text, nullable), add a check constraint enforcing exactly one of `encrypted_access_token` / `installation_id` non-null per `source_system` (data-model.md) — `backend/alembic/versions/`
- [ ] T007 Update the `Connector` model in `backend/src/models/connector.py` to match: `encrypted_access_token: str | None`, new `installation_id: str | None` column (depends on T006)
- [ ] T008 [P] Implement the `OAuthState` signed-token helper (issue/verify, HMAC over `{user_id, provider, purpose, nonce, exp}`, research.md §5) in `backend/src/services/oauth_svc.py` — stateless per data-model.md's noted implementation choice, no new table
- [ ] T009 Replace `WorkspaceRepository.get_by_owner` (`scalar_one_or_none()`) with `list_by_owner(owner_user_id) -> list[Workspace]` in `backend/src/repositories/workspace_repository.py` (research.md §4 — fixes the latent `MultipleResultsFound` bug)
- [ ] T010 Update `GET /me` in `backend/src/api/auth.py`: drop `workspace_id` from `MeResponse`, stop calling the now-removed `get_by_owner` (depends on T009)
- [ ] T011 [P] Add `ConnectorRepository.create_github_installation(workspace_id, installation_id, external_resource_ref)` (writes `installation_id`, leaves `encrypted_access_token` null) alongside the existing `create()` (renamed/kept for Notion's token path) in `backend/src/repositories/connector_repository.py` (depends on T007)
- [ ] T012 [P] Add `WorkspaceRepository.create` caller support for dashboard-driven creation — no signature change needed (`create(owner_user_id, name)` already exists), confirm it's called without any single-workspace assumption anywhere in `backend/src/services/workspace_svc.py`

**Checkpoint**: Foundation ready — user story work can begin.

---

## Phase 3: User Story 1 - Connect a GitHub repo without typing anything (Priority: P1) 🎯 MVP

**Goal**: A user clicks "Connect GitHub," completes GitHub's own installation screen, and lands back with a connector already created — no owner/repo string, no pasted token.

**Independent Test**: quickstart.md scenarios 1–3 (single repo, multi-repo picker, denial).

### Tests for User Story 1

- [ ] T013 [P] [US1] Unit tests for JWT signing and installation-token minting in `backend/tests/unit/test_oauth_svc.py`, using a fake RS256 private key fixture (never a real one — plan.md Testing) — cover expiry handling and a minting failure surfacing as `needs_reconnect`-eligible
- [ ] T014 [P] [US1] Contract tests for `GET /oauth/github/start`, `GET /oauth/github/callback` (single-repo, multi-repo, zero-repo/denied paths), and `POST /oauth/github/finalize` in `backend/tests/contract/test_oauth.py`
- [ ] T015 [P] [US1] Contract test: invalid/expired/replayed `state` on the GitHub callback is rejected and redirects to an error state, no connector created (spec.md Edge Cases) — `backend/tests/contract/test_oauth.py`
- [ ] T016 [P] [US1] Integration test: a repo picked during the multi-repo picker step but revoked before `finalize` confirms fails clearly, no broken connector row (spec.md Edge Cases) — `backend/tests/integration/test_github_oauth_flow.py`

### Implementation for User Story 1

- [ ] T017 [US1] Implement GitHub App JWT signing (RS256, `iat`/`exp`/`iss`) and installation-token minting (`POST /app/installations/{id}/access_tokens`) in `backend/src/services/oauth_svc.py` (depends on T008; makes T013 pass)
- [ ] T018 [US1] Implement `GET /oauth/github/start` in `backend/src/api/oauth.py` (new file) — issues a signed `state` (purpose `connector_github`), redirects to `https://github.com/apps/{app-slug}/installations/new`
- [ ] T019 [US1] Implement `GET /oauth/github/callback` in `backend/src/api/oauth.py` — verify `state`, mint installation token, call `GET /installation/repositories`; single-repo path creates the connector directly via T011's `create_github_installation`, multi-repo path redirects to the frontend picker, zero-repo/denied path redirects with a clear failure indicator (contracts/api.md) (depends on T017, T011)
- [ ] T020 [US1] Implement `POST /oauth/github/finalize` in `backend/src/api/oauth.py` — creates the connector from the user's picked repo (depends on T011)
- [ ] T021 [US1] Update `connector_svc.py`'s GitHub ingestion path in `backend/src/services/connector_svc.py` to mint a fresh installation token via `oauth_svc` at point of use instead of decrypting a stored PAT (depends on T017)
- [ ] T022 [US1] Update `github_connector.py` in `backend/src/connectors/github_connector.py` to accept a minted installation token as a parameter rather than a decrypted stored one (depends on T021)
- [ ] T023 [P] [US1] Replace the Connect page's GitHub token-paste form with a "Connect GitHub" button plus multi-repo picker UI in `frontend/src/app/connect/page.tsx`; show connected-repo state + disconnect/reconnect option when a connector already exists (spec.md Acceptance Scenario 4)
- [ ] T024 [P] [US1] Add `startGithubOAuth(workspaceId)` and the multi-repo `finalizeGithub()` call to `frontend/src/lib/api.ts`

**Checkpoint**: US1 fully functional and independently testable — run quickstart.md scenarios 1–3.

---

## Phase 4: User Story 2 - Connect a Notion workspace without typing anything (Priority: P2)

**Goal**: Same authorize-and-pick shape as US1, for Notion — no pasted integration token, no typed page IDs.

**Independent Test**: quickstart.md scenarios 4–5.

### Tests for User Story 2

- [ ] T025 [P] [US2] Contract tests for `GET /oauth/notion/start` and `GET /oauth/notion/callback` (success and denied paths) in `backend/tests/contract/test_oauth.py`
- [ ] T026 [P] [US2] Contract test: invalid/expired/replayed `state` on the Notion callback is rejected, no connector created — `backend/tests/contract/test_oauth.py`

### Implementation for User Story 2

- [ ] T027 [US2] Implement Notion code-for-token exchange (`POST https://api.notion.com/v1/oauth/token`) in `backend/src/services/oauth_svc.py` (research.md §2)
- [ ] T028 [US2] Implement `GET /oauth/notion/start` in `backend/src/api/oauth.py` — signed `state` (purpose `connector_notion`), redirect to `https://api.notion.com/v1/oauth/authorize`
- [ ] T029 [US2] Implement `GET /oauth/notion/callback` in `backend/src/api/oauth.py` — verify `state`, exchange `code`, call Notion `/v1/search` to enumerate shared pages, create the connector via the existing `ConnectorRepository.create()` (encrypted-token path, unchanged — research.md §2 confirms it's a drop-in), redirect with success/denial indicator (depends on T027)
- [ ] T030 [P] [US2] Replace the Connect page's Notion token-paste form with a "Connect Notion" button in `frontend/src/app/connect/page.tsx` (depends on T023 sharing the same file — sequence after US1's page edit lands)
- [ ] T031 [P] [US2] Add `startNotionOAuth(workspaceId)` to `frontend/src/lib/api.ts`

**Checkpoint**: US1 + US2 both work independently — run quickstart.md scenarios 1–5.

---

## Phase 5: User Story 3 - See all projects from one home screen (Priority: P3)

**Goal**: The home page becomes a dashboard listing every workspace the user owns, with an "Add new project" flow.

**Independent Test**: quickstart.md scenarios 6–8. Per spec.md, this is testable even if the connect flow underneath still used manual-token forms — but by this point in the phase order, US1/US2's OAuth flows are already in place, so it's exercised end-to-end.

### Tests for User Story 3

- [ ] T032 [P] [US3] Contract test for `GET /workspaces` — empty list for a zero-workspace user, correct inline connector statuses for a multi-workspace user — in `backend/tests/contract/test_workspaces.py`
- [ ] T033 [P] [US3] Regression test: `GET /me` for a user owning 2+ workspaces returns `200` with just `{user_id}`, no `MultipleResultsFound`/500 (quickstart.md scenario 8, research.md §4's originally-found bug) — `backend/tests/contract/test_workspaces.py`
- [ ] T034 [P] [US3] Integration test: "Add new project" creates a new workspace and the response/redirect routes directly into the GitHub/Notion connect flow — `backend/tests/integration/test_dashboard_flow.py`

### Implementation for User Story 3

- [ ] T035 [US3] Implement `GET /workspaces` in `backend/src/api/workspaces.py` — list every workspace owned by the caller with connectors' status inline (contracts/api.md), using `list_by_owner` (T009) and `ConnectorRepository.list_by_workspace` (existing) to avoid N+1 (depends on T009)
- [ ] T036 [US3] Add a `POST /workspaces` caller path (or confirm the existing one) is reachable from an authenticated "Add new project" action with no uniqueness check blocking a second workspace (depends on T009)
- [ ] T037 [US3] Turn `frontend/src/app/page.tsx` into the project dashboard: list workspaces with inline connector/ingestion status, empty state for zero workspaces (spec.md Acceptance Scenario 1)
- [ ] T038 [US3] Implement `frontend/src/app/projects/new/page.tsx` — creates a workspace via `POST /workspaces` then routes straight into `connect/page.tsx` for it
- [ ] T039 [P] [US3] Add `listWorkspaces()` to `frontend/src/lib/api.ts` (depends on T035)
- [ ] T040 [US3] Confirm selecting an existing project from the dashboard opens that workspace's own `/status` and `/ask` views unchanged from Phase 1 (spec.md Acceptance Scenario 4) — wire the dashboard's per-project link, no new page needed

**Checkpoint**: All three of US1/US2/US3 independently functional — run quickstart.md scenarios 1–8.

---

## Phase 6: User Story 4 - Sign in with Google or GitHub (Priority: P4)

**Goal**: "Continue with Google" / "Continue with GitHub" alongside the existing magic-link flow, landing on the same account when emails match.

**Independent Test**: quickstart.md scenario 9. Fully independent of US1-US3 — no backend contract change (contracts/api.md — handled entirely by the Supabase client SDK).

### Tests for User Story 4

- [ ] T041 [P] [US4] Integration test: a user who signed in via magic-link email, then signs in again via Google/GitHub with the matching confirmed email, lands on the same `user_id` — no duplicate account (spec.md User Story 4 Scenario 3) — `backend/tests/integration/test_social_signin_merge.py` (verifies Supabase's own account-linking behavior end-to-end against the auth response, not a ContextOS-owned code path)

### Implementation for User Story 4

- [ ] T042 [P] [US4] Add "Continue with Google" and "Continue with GitHub" buttons to the sign-in page, calling `supabase.auth.signInWithOAuth({ provider: 'google' | 'github' })`, in `frontend/src/app/**/sign-in` (wherever Phase 1's magic-link sign-in page currently lives)
- [ ] T043 [P] [US4] Confirm Supabase's OAuth redirect URIs (for both providers) are registered for the deployed frontend origin — dashboard configuration, note alongside T003

**Checkpoint**: All four user stories independently functional — full quickstart.md pass.

---

## Phase 7: Polish & Cross-Cutting Concerns

- [ ] T044 [P] Update `docs/prd.md` to record the multi-workspace-per-user scope change (plan.md's Constitution Check, Principle V — required in the same change, not left to silently diverge)
- [ ] T045 [P] Update `docs/roadmap.md`: move OAuth token acquisition (Phase 2 open question) and the relevant slice of multi-workspace (Phase 6) to reflect what this feature actually delivered
- [ ] T046 [P] **Regression check**: confirm the `connectors` check constraint (T006) actually rejects a row with both `installation_id` and `encrypted_access_token` set, and one with neither — `backend/tests/unit/test_connector_token_shape.py`
- [ ] T047 [P] **Regression check**: confirm `installation_id` is never logged or returned outside a `workspace_id`-scoped read path (Constitution Principle VI) — extend `backend/tests/unit/test_workspace_isolation.py`
- [ ] T048 Remove the now-dead manual PAT/integration-token paste forms and their backend endpoints if fully superseded by T018-T020/T028-T029 — confirm no quickstart.md scenario from feature 001 still depends on them before deleting (CLAUDE.md: don't leave half-finished old and new paths side by side)
- [ ] T049 Run the full quickstart.md validation pass for this feature — all 9 scenarios — before calling it done (constitution's `validation` step, not a claim on faith)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: no dependencies — T001-T003 are account/dashboard steps that can run alongside T004-T005
- **Foundational (Phase 2)**: depends on Setup — blocks all user stories (the `Connector` model/migration change and `OAuthState` helper are shared by US1 and US2; the `WorkspaceRepository` fix is shared by US3)
- **User Story 1 (Phase 3)**: depends on Foundational only
- **User Story 2 (Phase 4)**: depends on Foundational; shares `frontend/src/app/connect/page.tsx` with US1 (T030 sequenced after T023) but its backend path (`oauth.py`, `oauth_svc.py` additions) is independent
- **User Story 3 (Phase 5)**: depends on Foundational (T009's `list_by_owner`); benefits from US1/US2 existing to be a meaningful end-to-end demo, but `GET /workspaces` and the dashboard shell don't strictly require either OAuth flow to be built first (spec.md's own Independent Test note)
- **User Story 4 (Phase 6)**: depends on nothing but Setup (T003) — fully independent of US1/US2/US3, could be built in parallel by a second developer
- **Polish (Phase 7)**: depends on all four user stories being complete

### Within Each User Story

- Tests written and confirmed failing before implementation
- `oauth_svc.py` primitives (JWT/token minting, code exchange, state verification) before the API endpoints that call them
- Backend endpoints before the frontend pages that call them
- Story complete and independently validated before moving to the next priority

### Parallel Opportunities

- T001-T003 (account/dashboard setup) can run in parallel with each other and with T004-T005
- All `[P]` Foundational tasks (T008, T011, T012) can run in parallel once T006/T007/T009 land
- US1 and US4 can be built fully in parallel (no shared files, no shared backend logic)
- US1's tests (T013-T016) can run in parallel with each other; same for US2's (T025-T026), US3's (T032-T034)

---

## Parallel Example: User Story 1

```bash
# Tests first, in parallel:
Task: "Unit tests for JWT signing/installation-token minting in backend/tests/unit/test_oauth_svc.py"
Task: "Contract tests for GET /oauth/github/start, /callback, POST /oauth/github/finalize in backend/tests/contract/test_oauth.py"
Task: "Contract test: invalid/expired/replayed state rejected in backend/tests/contract/test_oauth.py"
Task: "Integration test: repo access revoked mid-flow fails cleanly in backend/tests/integration/test_github_oauth_flow.py"

# Frontend work, in parallel with each other (not with the backend endpoints they call):
Task: "Connect page GitHub button + multi-repo picker in frontend/src/app/connect/page.tsx"
Task: "startGithubOAuth()/finalizeGithub() in frontend/src/lib/api.ts"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Phase 1: Setup (at minimum T001, T004, T005 — T002/T003 not needed until US2/US4)
2. Phase 2: Foundational (blocks everything else)
3. Phase 3: User Story 1
4. **Stop and validate** against quickstart.md scenarios 1-3
5. This alone closes the single highest-friction point spec.md identifies (GitHub OAuth connect) and is independently demoable per spec.md's own Independent Test note

### Incremental Delivery

1. Setup + Foundational → foundation ready
2. User Story 1 → validate → highest-friction fix shipped
3. User Story 2 → validate → second connector friction point closed
4. User Story 3 → validate → dashboard/multi-project structure in place
5. User Story 4 → validate (can be done any time after Setup, in parallel with 2-4) → sign-in convenience
6. Polish → full quickstart.md pass, doc updates, regression checks, dead-code removal

### Parallel Team Strategy

With multiple developers:

1. Team completes Setup + Foundational together
2. Once Foundational is done:
   - Developer A: User Story 1, then User Story 2 (shares the Connect page)
   - Developer B: User Story 4 (fully independent) then joins User Story 3
3. User Story 3's backend (`GET /workspaces`, T035) can start as soon as Foundational's `list_by_owner` (T009) lands, ahead of US1/US2 finishing, since it only reads existing connector state

---

## Notes

- `[P]` = different files, no dependency on an incomplete task
- Commit after each task or logical group (per CLAUDE.md conventions — no `Co-Authored-By` trailer)
- Stop at each checkpoint and actually run the relevant quickstart.md scenario before moving on — don't just mark tasks complete on faith
- Never commit a real GitHub App private key or Notion client secret — T001/T002's credentials belong in `backend/.env` (gitignored) and deployment platform secrets only, per `docs/decisions/ADR-001-weekend-mvp-stack.md`'s existing convention for `GROQ_API_KEY`/`VOYAGE_API_KEY`
