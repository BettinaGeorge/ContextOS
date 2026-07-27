# Phase 1 Data Model: OAuth Connectors & Project Dashboard

Extends `specs/001-trace-doc-to-code/data-model.md`. Only entities that change or are newly introduced are listed below — everything else (Artifact, Relationship, Job) is untouched by this feature.

## Workspace (changed cardinality, not shape)

Same fields as feature 001. What changes is the *relationship* to a user, not the table:

**Was**: unenforced but assumed 1:1 with `owner_user_id` (`WorkspaceRepository.get_by_owner` used `scalar_one_or_none()`).
**Now**: explicit 1:N. `get_by_owner` is replaced with `list_by_owner(owner_user_id) -> list[Workspace]`. No new column — `owner_user_id` already permits multiple rows; the fix is in the repository method and the API surface built on it (contracts/api.md), not the schema.

## Connector (changed — GitHub path only)

| Field | Type | Notes |
|---|---|---|
| id | uuid, PK | unchanged |
| workspace_id | uuid, FK → workspace | unchanged |
| source_system | enum(`github`, `notion`) | unchanged |
| status | enum(`connected`, `ingesting`, `complete`, `failed`, `needs_reconnect`) | unchanged |
| encrypted_access_token | text, **now nullable** | **Notion**: unchanged — still holds the OAuth access token, encrypted, decrypted at use exactly like the old internal-integration token was (research.md §2). **GitHub**: NULL going forward — a GitHub App installation has no long-lived token to store here. |
| **installation_id** | text, nullable | **NEW.** GitHub only. The GitHub App installation ID for this connector. Not a secret on its own (meaningless without the App's private key, held once in application config — data-model note, not per-row), but still workspace-scoped and access-controlled like every other connector field (Constitution Principle VI). |
| external_resource_ref | text | unchanged in meaning (repo `owner/name` for GitHub, selected page ids for Notion) — for GitHub, now populated from the installation's granted repository list rather than user-typed text. |
| last_ingested_at | timestamptz, nullable | unchanged |
| error_message | text, nullable | unchanged |
| created_at / updated_at | timestamptz | unchanged |

**Validation rule (new)**: exactly one of `encrypted_access_token` / `installation_id` is non-null, enforced by a check constraint — `source_system = 'github'` rows must have `installation_id` set and `encrypted_access_token` null; `source_system = 'notion'` rows must have `encrypted_access_token` set and `installation_id` null. Prevents a connector existing in an ambiguous half-migrated state.

**State transitions**: unchanged from feature 001 (`connected` → `ingesting` → `complete`/`failed`, `needs_reconnect` on auth failure). New trigger into `needs_reconnect`: an installation-token mint call failing because the installation was revoked externally (spec.md Edge Cases) — same terminal state Phase 1 already defined for GitHub PAT revocation, not a new status value.

## OAuthState (new — transient, not part of the canonical artifact/relationship model)

Backs CSRF protection across the two connector-OAuth redirects (research.md §5). Short-lived by design — not meant to accumulate.

**Correction (post-review)**: an earlier draft also defined `signin_google`/`signin_github` purposes for this entity, on the assumption it would also back sign-in OAuth's CSRF handling. Removed — contracts/api.md is explicit that sign-in OAuth (spec.md User Story 4) is handled entirely by Supabase's own hosted `signInWithOAuth` flow, with no new ContextOS endpoint and therefore no ContextOS-issued state token involved. Supabase manages its own CSRF protection for that redirect. `OAuthState` exists only for the two connector-OAuth purposes below.

| Field | Type | Notes |
|---|---|---|
| id | uuid, PK | |
| user_id | text | the authenticated user initiating the connector-OAuth redirect (always set — unlike a sign-in flow, a connector-OAuth redirect only ever starts from an already-authenticated session) |
| purpose | enum(`connector_github`, `connector_notion`) | |
| workspace_id | uuid, FK → workspace | the workspace the resulting connector will attach to |
| nonce | text | random, included in the signed state value |
| expires_at | timestamptz | short TTL (minutes, not hours) — a state token is only ever alive for the duration of one redirect round-trip |
| created_at | timestamptz | |

**Validation rule**: a state row is deleted (or marked consumed) on first successful verification — replay of the same state value after use must fail, standard OAuth CSRF hygiene.

**Note**: implementation may choose to make this a signed, stateless token (HMAC payload, no DB row at all) instead of a real table — research.md §5 leaves this as an implementation choice for `/speckit-tasks`, not a data-model requirement. Documented here as a logical entity either way, since its fields and validation rule are the same regardless of storage form.
