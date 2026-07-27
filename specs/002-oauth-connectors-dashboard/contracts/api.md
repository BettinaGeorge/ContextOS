# API Contract Additions/Changes: OAuth Connectors & Project Dashboard

Extends `specs/001-trace-doc-to-code/contracts/api.md`. Only new or changed endpoints are listed. All endpoints below require `Authorization: Bearer <supabase-jwt>` except the two `/callback` redirects, which authenticate via the signed `state` parameter instead (the browser arrives there mid-redirect, not carrying the app's own bearer token — standard OAuth callback shape).

Sign-in via Google/GitHub OAuth (spec.md User Story 4) is **not** a backend contract change — it's handled entirely by the Supabase client SDK (`supabase.auth.signInWithOAuth`) already in use for the existing magic-link flow, redirecting through Supabase's own hosted callback. No new ContextOS endpoint is needed for sign-in.

## `GET /me` (changed)

**200**
```json
{ "user_id": "string" }
```
`workspace_id` is removed — replaced by `GET /workspaces` below, since a user may now own more than one.

## `GET /workspaces` (new)

Lists every workspace the caller owns, each with its connectors' status inline so the dashboard (User Story 3) can render without N follow-up requests.

**200**
```json
[
  {
    "id": "string",
    "name": "string",
    "created_at": "iso8601",
    "connectors": [
      {
        "source_system": "github | notion",
        "status": "connected | ingesting | complete | failed | needs_reconnect"
      }
    ]
  }
]
```
`[]` if the caller owns no workspaces yet (spec.md User Story 3, Scenario 1 — empty state).

## `GET /oauth/github/start` (new)

**Query**: `workspace_id` (the workspace to attach the resulting connector to).

**302**: redirects to GitHub's App installation URL (`https://github.com/apps/{app-slug}/installations/new`) with a signed `state` parameter (data-model.md `OAuthState`, purpose `connector_github`) round-tripped through the redirect.

## `GET /oauth/github/callback` (new)

GitHub redirects here after installation with `installation_id`, `setup_action`, and `state` query params.

**Behavior**: verify `state` (reject and redirect to an error state on the frontend if invalid/expired/replayed — spec.md Edge Cases). Mint a short-lived installation token (research.md §1), call `GET /installation/repositories` to see what was granted.

- **Exactly one repository granted**: create the `Connector` row (`installation_id` set, `external_resource_ref` = that repo's `owner/name`) and redirect to the frontend Connect page with a success indicator.
- **More than one repository granted**: redirect to a lightweight frontend picker (still zero typing — a list of the granted repos to choose exactly one from, per PRD §4's one-repo-per-workspace constraint) which then calls a follow-up endpoint (`POST /oauth/github/finalize` — see below) with the chosen repo.
- **Zero repositories granted / installation denied**: redirect to the frontend with a clear "connection wasn't completed" state (spec.md Edge Cases, Acceptance Scenario 3) — no connector row created.

## `POST /oauth/github/finalize` (new)

Only reached when the installation granted more than one repository and the user picked one from the follow-up picker.

**Request**: `{ "installation_id": "string", "repo": "owner/name" }`
**201**: `{ "connector_id": "string", "status": "connected" }` — same JSON body as `POST /connectors/github`'s existing `202` response, but `201` here since the connector is already fully created by the time this call returns (no separate async step to accept, unlike the original endpoint).

## `GET /oauth/notion/start` (new)

**Query**: `workspace_id`.

**302**: redirects to `https://api.notion.com/v1/oauth/authorize` with a signed `state` (purpose `connector_notion`).

## `GET /oauth/notion/callback` (new)

Notion redirects here with `code` and `state`.

**Behavior**: verify `state`. Exchange `code` for an access token at `https://api.notion.com/v1/oauth/token` (research.md §2). Call Notion's `/v1/search` with the new token to enumerate what was shared, create the `Connector` row (`encrypted_access_token` set, `external_resource_ref` = the discovered page ids — no typing required, closing FR-003), redirect to the frontend Connect page with a success indicator.

**Denied/cancelled**: same shape as the GitHub callback's denial case — clear "connection wasn't completed" state, no connector row created.

## Error shape

Unchanged from feature 001: `{ "error": "string", "detail": "string | null" }`. OAuth-specific failures (invalid state, provider denial, installation revoked mid-flow) all route through this same shape on the frontend-facing redirect's query string (e.g. `?error=oauth_denied`), not a raw JSON body, since these are browser redirects, not fetch() calls.
