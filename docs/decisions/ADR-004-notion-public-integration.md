# ADR-004: Notion public integration (OAuth) for Notion connector setup

Status: Accepted.

## Context

Feature 002 replaces manual integration-token + hand-typed page ID entry for the Notion connector with an OAuth-based authorize-and-pick flow, the second half of closing `docs/prd.md` §10's deferred decision. Phase 1 used an **internal integration** — a token scoped to one workspace, with no OAuth flow and no page-discovery mechanism, which is exactly why page IDs had to be typed by hand. Notion offers a second integration type, **public integrations**, that use a real OAuth 2.0 flow.

## Decision

Convert to a **Notion public integration**, using the standard OAuth 2.0 authorization code flow (`GET /v1/oauth/authorize` → Notion's own hosted consent screen, where the user picks which pages/databases to share → redirect with `code` → `POST /v1/oauth/token` for the access token).

| Aspect | Choice | Why |
|---|---|---|
| Page selection | Notion's own OAuth consent screen | The user selects which pages to share with the integration as part of authorizing — this *is* the picker FR-003 asks for, so ContextOS doesn't need to build custom page-discovery UI for the common case. Verified against Notion's own API documentation, not assumed. |
| Token lifecycle | Long-lived, unchanged pattern | Unlike GitHub App installation tokens, a Notion OAuth access token **does not expire on a schedule** — it stays valid until the user revokes it. This is a genuine drop-in replacement for the existing `encrypted_access_token` column and `decrypt_for_use` pattern (`connector_repository.py`); no token-refresh logic is needed on the Notion side, unlike the GitHub side (ADR-003). |
| Discovery of what was shared | `POST /v1/search` with the new token | After token exchange, calling Notion's search endpoint with the fresh token enumerates exactly what was shared during consent — this populates `external_resource_ref` (the page ids) automatically, closing FR-003's "no manually typed page IDs" requirement without any new UI. |

## Consequences

- `NotionConnector`'s existing `ingest_full()`/`normalize_artifact()` logic is unchanged — it already operates on a token + a list of page ids; only *how* `page_ids` gets populated changes (discovered via `/v1/search` after OAuth, instead of a user-typed comma-separated string).
- `Connector.encrypted_access_token` keeps working exactly as it does today for Notion rows — no schema change needed on the Notion side beyond what GitHub's `installation_id` addition already requires as a shared table (`data-model.md`'s mutual-exclusivity constraint is about the row's `source_system`, not a Notion-specific change).
- A new external setup step exists: converting the existing internal integration to public (or registering a new public one) in Notion's integrations dashboard — client ID, client secret, redirect URI. One-time, free, non-code, same category as the original internal-integration setup already done for Phase 1. No budget impact.
- The existing internal-integration token (`NOTION_TOKEN` in `backend/.env`) becomes unused by the primary connect path once this ships — left in place as a reference/fallback value during migration, not deleted as part of this ADR (an implementation-phase cleanup decision, not an architecture one).

## Alternatives considered

- **Keep the internal integration, improve the UX around typing the token/page IDs** — rejected. Internal integrations have no consent/discovery flow at all; there's no way to satisfy FR-003's "no manually typed page IDs" requirement without the OAuth mechanism itself, regardless of how the surrounding form is styled.
- **Use Supabase's GitHub sign-in provider's `provider_token` as a shortcut for connector access** (considered for GitHub, and by extension asked whether an equivalent shortcut exists for Notion) — not applicable to Notion at all (Supabase doesn't offer a Notion sign-in provider), and already rejected on the GitHub side per `docs/prd.md` §10's own finding that Supabase doesn't persist `provider_token` past the callback moment — unusable for a connector that needs to ingest again later. Recorded here for completeness since the question was evaluated for both providers together during planning.
