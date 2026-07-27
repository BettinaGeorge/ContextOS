# ADR-003: GitHub App (not classic OAuth App) for GitHub connector setup

Status: Accepted.

## Context

Feature 002 (`specs/002-oauth-connectors-dashboard/`) replaces manual PAT entry for the GitHub connector with an OAuth-based authorize-and-pick flow, closing the deferred decision recorded in `docs/prd.md` §10. Two real options exist for "OAuth-based GitHub access": a classic OAuth App, or a GitHub App. They are not interchangeable — GitHub treats them as genuinely different integration types with different authentication mechanics, not two flavors of the same thing.

## Decision

Register a **GitHub App**, not a classic OAuth App.

| Aspect | Choice | Why |
|---|---|---|
| Repo selection | GitHub App installation screen | GitHub's own hosted installation UI lets the user choose specific repositories (or "all repositories") at grant time — this *is* the repo picker FR-002 asks for, so ContextOS doesn't have to build one for the common case. A classic OAuth App's `repo` scope is all-or-nothing across every repo the user can access; there is no native picker. Verified against GitHub's own documentation, not assumed. |
| Token lifecycle | Installation access tokens, minted on demand | A GitHub App authenticates as an *installation*, not as a stored user token. Getting a usable token requires signing a JWT with the App's private key, then exchanging it at `POST /app/installations/{id}/access_tokens` — the result **expires after 1 hour**. There is nothing long-lived to encrypt and store per connector the way Phase 1's PAT was; `installation_id` is stored instead (`data-model.md`), and a fresh token is minted at the point of use (ingestion time). |
| Blast radius | Narrower than a classic OAuth App | Installing scoped to specific repos, plus tokens that expire in an hour even if somehow exfiltrated, is a real security improvement over both the old PAT (long-lived, workspace-wide scope on GitHub's side even if the user picked one repo to type in) and a classic OAuth App (`repo` scope covers everything, indefinitely, until manually revoked). |

## Consequences

- `connector_svc.py`'s GitHub path changes shape: instead of `decrypt_for_use(connector)` returning one long-lived token, it now signs a JWT (App private key, held once in application config — `GITHUB_APP_PRIVATE_KEY`, `GITHUB_APP_ID`) and exchanges it for a fresh installation token before every ingestion run. This is a real code change, not a config-only swap — the "encrypted token at rest" pattern (Constitution Principle III) still applies to what's stored (nothing per-connector is secret without the App's private key), but the *mechanism* is now mint-on-demand rather than decrypt-and-use.
- `Connector.encrypted_access_token` becomes nullable for GitHub rows (`installation_id` is used instead); a check constraint enforces exactly one of the two being set per row, keyed by `source_system` (`data-model.md`).
- A new external setup step exists: registering the GitHub App itself (App ID, private key, installation URL) in GitHub's developer settings — a one-time, free, non-code step, same category as the Supabase project setup already done in ADR-001. No budget impact ($0, no payment method required — confirmed, same as PAT/OAuth App registration).
- If an installation is revoked externally (user removes the App's access from GitHub settings) after a repo is connected, the next installation-token mint fails and the connector transitions to `needs_reconnect` — the same terminal state Phase 1 already defined for PAT revocation, not a new status value (`data-model.md`).

## Alternatives considered

- **Classic OAuth App with `repo` scope** — rejected. Inferior UX for exactly what this feature exists to fix (no native repo picker; GitHub's own docs point at Apps as the preferred pattern for this shape of integration), and doesn't improve on the "blanket repo access" trade-off `docs/prd.md` §10 already flagged as an accepted-but-imperfect cost of moving off PATs — a GitHub App genuinely narrows that trade-off instead of just relocating it.
- **Continue with manual PAT entry** — rejected by definition; this ADR exists because that's the friction being removed.
- **GitHub App, but store a long-lived token by never letting the installation token expire in the request path (fetch once, cache, refresh only on 401)** — considered and rejected as needless complexity for this project's actual scale (single-connector ingestion runs, not high-frequency API calls); minting fresh at the start of each ingestion run is simpler and correctness-first, matching Constitution Principle V (narrowest credible scope). Revisit only if real usage shows the extra mint call is a meaningful cost.
