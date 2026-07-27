# Quickstart: Validate OAuth Connectors & Project Dashboard

A runnable guide to prove this feature works end-to-end against the acceptance scenarios in `spec.md`. Not a tutorial — this is what "done" gets checked against.

## Prerequisites

- Everything from `specs/001-trace-doc-to-code/quickstart.md` (this feature builds on that MVP, doesn't replace it).
- A registered **GitHub App** (not a classic OAuth App — research.md §1): App ID, a generated private key, a public installation URL. Installed on a test GitHub account with at least two repositories (to exercise the "more than one repo granted" picker path, contracts/api.md).
- A **Notion public integration** (research.md §2): client ID, client secret, redirect URI registered in Notion's integration dashboard. Requires converting the existing Phase 1 internal integration to public, or registering a new one.
- Google and GitHub sign-in providers enabled in the Supabase project's Authentication → Providers settings (account/dashboard configuration, not code — same category of setup as the Supabase project itself in Phase 1).
- New env vars: `GITHUB_APP_ID`, `GITHUB_APP_PRIVATE_KEY`, `NOTION_OAUTH_CLIENT_ID`, `NOTION_OAUTH_CLIENT_SECRET`. (An earlier draft also listed `GITHUB_APP_CLIENT_ID`/`GITHUB_APP_CLIENT_SECRET` — removed; the GitHub App installation flow authenticates via JWT + private key only, per research.md §1/ADR-003, not a client-id/secret code exchange.)

## Validation scenarios

### 1. GitHub OAuth connect, single repo granted (User Story 1, Scenarios 1–2)

1. From a workspace with no GitHub connector, click "Connect GitHub."
2. Complete GitHub's installation screen, granting access to exactly one repository.

**Expected**: redirected back already connected — a `Connector` row exists with `installation_id` set and the correct `owner/name`, no token ever typed or pasted (SC-001).

### 2. GitHub OAuth connect, multiple repos granted (User Story 1, Scenario 1 variant)

1. Same as above, but grant access to two or more repositories during installation.

**Expected**: redirected to a picker listing the granted repos; selecting one finalizes the connector (`POST /oauth/github/finalize`) scoped to exactly that repo (PRD §4's one-repo-per-workspace constraint still holds).

### 3. GitHub OAuth denial (User Story 1, Scenario 3)

1. Start the GitHub connect flow, then cancel/deny at GitHub's screen.

**Expected**: returned to ContextOS with a clear "connection wasn't completed" state — no connector row created, no partial state (`GET /connectors` still shows none for GitHub).

### 4. Notion OAuth connect (User Story 2, Scenarios 1–2)

1. From a workspace with no Notion connector, click "Connect Notion."
2. Complete Notion's consent screen, selecting one or more pages to share.

**Expected**: redirected back already connected — a `Connector` row exists with `encrypted_access_token` set and `external_resource_ref` populated from what was actually shared, no token or page ID ever typed (SC-002).

### 5. Notion OAuth denial (User Story 2, Scenario 3)

1. Start the Notion connect flow, then cancel/deny at Notion's screen.

**Expected**: same shape as Scenario 3 above — clear failure state, no connector row.

### 6. Dashboard empty state (User Story 3, Scenario 1)

1. Sign in as a user who owns zero workspaces.

**Expected**: `GET /workspaces` returns `[]`; the home page shows an empty state prompting the user to add their first project, not an error or blank screen.

### 7. Dashboard with multiple projects (User Story 3, Scenarios 2–4)

1. As a user who owns 2+ workspaces (mix of fully-connected and not-yet-connected), load the home page.

**Expected**: all workspaces listed with each one's connector status visible without opening it (SC-003); "Add new project" creates a new workspace and routes directly into the connect flow (Scenarios 1/4 above); selecting an existing project opens that workspace's own `/status` and `/ask` views unchanged from Phase 1.

### 8. Multi-workspace regression check (plan.md's flagged latent bug)

1. With a user who now owns 2+ workspaces, call `GET /me`.

**Expected**: `200` with just `{ "user_id": ... }` — no `MultipleResultsFound` exception, no 500. This is the concrete regression test for the bug research.md §4 found in `WorkspaceRepository.get_by_owner`'s original `scalar_one_or_none()`.

### 9. Social sign-in (User Story 4, Scenarios 1–3)

1. From the sign-in page, click "Continue with Google," complete the consent screen.
2. Repeat with "Continue with GitHub."
3. Using an email that previously signed in via magic-link, sign in again via Google/GitHub with the same email.

**Expected**: both provider sign-ins land the user in an authenticated session (SC-005 — zero required free-text input beyond the provider's own consent click). Scenario 3 lands on the **same** account/user id as the original magic-link sign-in — no duplicate account (resolved clarification, spec.md User Story 4 Scenario 3).

## Out of scope for this validation pass

Per spec.md's Assumptions and FR-009: team/shared workspace access, multi-repo-per-workspace, and any manual-token fallback path are not covered here — none of them are in this feature's scope.
