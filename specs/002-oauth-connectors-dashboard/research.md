# Phase 0 Research: OAuth Connectors & Project Dashboard

No `NEEDS CLARIFICATION` markers remain in `plan.md`'s Technical Context after this research. Findings below are from real provider documentation, not assumption — this is exactly the class of detail the constitution's "verify against the real API, not assumed" standard (set by ADR-002) applies to.

## 1. GitHub connector: GitHub App vs. classic OAuth App

**Decision**: Register a **GitHub App**, not a classic OAuth App.

**Rationale**: GitHub Apps let the user choose specific repositories (or "all repositories") during the app's own hosted *installation* screen — this is GitHub's native repo picker, so ContextOS doesn't need to build one for the common case. A classic OAuth App's `repo` scope is all-or-nothing across every repository the user can access; GitHub's own docs describe Apps as "generally preferred... because they use fine-grained permissions and give the user more control over which repositories the app can access." This directly satisfies FR-002 ("no manually typed owner/repo string... in the primary path") better than an OAuth App would, and narrows the token's blast radius closer to Phase 1's PAT scoping than an OAuth App's blanket grant would (a partial win on the trade-off docs/prd.md §10 already flagged as accepted-but-imperfect).

**Real consequence, not a drop-in swap**: GitHub Apps authenticate as an *installation*, not as a stored user token. Getting a usable API token requires: (1) a JWT signed with the App's private key (RS256, `iat`/`exp`/`iss` claims — `PyJWT`, already a dependency), (2) exchanging that JWT for an installation access token via `POST /app/installations/{installation_id}/access_tokens`, which **expires after 1 hour**. There is no long-lived token to encrypt-and-store the way Phase 1's PAT was. What must be stored per-connector is the `installation_id` (not secret on its own — it's meaningless without the App's private key, which lives once at the application level in config, not per-connector) — see data-model.md.

**Alternatives considered**: Classic OAuth App with `repo` scope — rejected as the inferior UX for exactly what FR-002 asks for (GitHub's own docs point at Apps as the preferred pattern for this shape of integration) and it doesn't remove the "blanket repo access" trade-off the PRD already flagged. Continuing with manual PAT — the entire reason this feature exists; rejected by definition.

## 2. Notion connector: public integration (OAuth) vs. continuing with internal-integration tokens

**Decision**: Convert to a **Notion public integration**, using the standard OAuth 2.0 authorization code flow (`GET https://api.notion.com/v1/oauth/authorize` → user consents and picks pages on Notion's own hosted screen → redirect with `code` → `POST https://api.notion.com/v1/oauth/token` for the access token).

**Rationale**: Notion's own consent screen *is* the page/database picker — the user selects which pages to share with the integration as part of authorizing, satisfying FR-003 ("no manually typed page IDs... in the primary path") without ContextOS building a custom picker UI for the common case. Unlike GitHub's installation tokens, **the resulting access token does not expire on a schedule** — it stays valid until the user revokes it. This means Notion's OAuth token is a genuine drop-in replacement for the current `encrypted_access_token` column and `decrypt_for_use` pattern (`connector_repository.py`) — no new token-refresh logic needed on the Notion side, unlike GitHub.

**Consequence to note**: switching from an internal to a public integration is a one-time change in Notion's own integrations dashboard (registering the integration as public, setting a redirect URI, getting a client ID/secret) — a real setup step, same category as the original internal-integration setup already done for Phase 1, not a code-only change.

**Alternatives considered**: Keep the internal-integration token and just improve the UX around typing it — rejected, doesn't satisfy FR-003's "no manually typed page IDs" requirement, since internal integrations have no page-discovery/consent flow at all (that's the whole reason Phase 1 required hand-typing page IDs).

## 3. Sign-in OAuth (Google/GitHub) vs. connector OAuth — same or separate?

**Decision**: Fully separate, per spec.md's Assumptions. Sign-in uses **Supabase Auth's built-in Google and GitHub providers** (`supabase.auth.signInWithOAuth({ provider: 'google' | 'github' })`) — Supabase handles the entire flow and issues the same kind of session/JWT the app already verifies today (`core/auth.py`, unchanged). Connector access uses the GitHub App / Notion public integration described above, entirely independent of how the user signed in.

**Rationale**: Conflating the two would mean a user's GitHub *sign-in* token would need `repo` scope just in case they later connect a repo (over-broad, granted at the wrong moment, and revoked/rotated on a different lifecycle than a sign-in session should be). Keeping them separate also matches docs/prd.md §10's existing note that Supabase doesn't persist `provider_token` past the OAuth callback moment — that fact is only a problem if the plan depended on it, and this plan doesn't: the GitHub App installation flow and Notion's OAuth flow each mint and store their own tokens independently of Supabase's sign-in session.

**Alternatives considered**: Using Supabase's GitHub sign-in provider's transient `provider_token` directly as the connector token — rejected outright per docs/prd.md §10's own finding: Supabase doesn't persist it, so it's unusable for a connector that needs to ingest again later, not just at the moment of first sign-in.

## 4. Multi-workspace-per-user: what actually has to change

**Decision**: `WorkspaceRepository.get_by_owner(owner_user_id) -> Workspace | None` (uses `scalar_one_or_none()`) is replaced with `list_by_owner(owner_user_id) -> list[Workspace]`. `GET /me`'s `MeResponse.workspace_id: str | None` is removed in favor of a new `GET /workspaces` endpoint returning the list (contracts/api.md).

**Rationale**: Verified directly against the running code, not assumed — `POST /workspaces` (`api/workspaces.py`) has no uniqueness check today, so nothing has ever actually prevented a user from owning two workspaces. `get_by_owner`'s `scalar_one_or_none()` would raise `sqlalchemy.exc.MultipleResultsFound` the moment that happened. This feature is what finally exercises that path, so it's the right place to fix it rather than carry a latent crash forward.

**Alternatives considered**: Add a uniqueness constraint to keep single-workspace-per-user and build the "dashboard" as a single-project view with no list — rejected, this is precisely the capability spec.md FR-007/User Story 3 asks for.

## 5. CSRF / state handling across both OAuth flows

**Decision**: A signed, short-lived `state` token (HMAC over `{user_id, provider, purpose, nonce, exp}`, reusing the same secret-signing pattern already established for connector-token encryption) is generated before redirecting to either provider and verified on callback before any token exchange happens.

**Rationale**: Standard OAuth CSRF mitigation, required regardless of provider — both GitHub App installations and Notion's authorize endpoint support an opaque `state` parameter round-tripped through the redirect.

**Alternatives considered**: Session-stored state (server-side session keyed by a cookie) — rejected as unnecessary added state; a signed, stateless token needs no new storage and matches the project's existing "no separate session store" pattern (research.md item 2 in feature 001).
