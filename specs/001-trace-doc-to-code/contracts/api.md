# API Contract: Trace a Spec/Doc to Code

REST, JSON. All endpoints except `POST /workspaces` require `Authorization: Bearer <supabase-jwt>` and operate only on the caller's own workspace (Constitution Principle VI).

## `GET /me`

Returns the authenticated user's identity and their workspace, if one exists.

**200**
```json
{ "user_id": "string", "workspace_id": "string | null" }
```

## `POST /workspaces`

Creates the caller's one workspace. **409** if the caller already has one (Phase 1 is single-workspace-per-user).

**Request**: `{ "name": "string" }`
**201**: `{ "id": "string", "name": "string", "created_at": "iso8601" }`

## `POST /connectors/github`

Begins a GitHub connection for the caller's workspace. **409** if a GitHub connector already exists for this workspace (FR-002 / data-model.md unique constraint).

**Request**: `{ "repo": "owner/name", "auth_code_or_token": "string" }`
**202**: `{ "connector_id": "string", "status": "connected" }` — ingestion is triggered separately via `POST /ingest/{connector_id}`.

## `POST /connectors/notion`

Begins a Notion connection. Same 409 rule as above, scoped to `source_system = notion`.

**Request**: `{ "integration_token": "string", "page_ids": ["string", ...] }`
**202**: `{ "connector_id": "string", "status": "connected" }`

## `GET /connectors/{connector_id}/status`

**200**
```json
{
  "connector_id": "string",
  "source_system": "github | notion",
  "status": "connected | ingesting | complete | failed | needs_reconnect",
  "last_ingested_at": "iso8601 | null",
  "error_message": "string | null"
}
```
Satisfies FR-014 / User Story 3.

## `POST /ingest/{connector_id}`

Enqueues a full ingestion job (data-model.md Job entity). **202**: `{ "job_id": "string", "status": "queued" }`

## `GET /ingest/{job_id}/status`

**200**: `{ "job_id": "string", "status": "queued | running | complete | failed", "error_message": "string | null" }`

## `POST /ask`

The core workflow endpoint (User Story 1/2).

**Request**: `{ "question": "string", "notion_doc_url": "string | null" }`

**200 — answered with evidence**
```json
{
  "answer": "string",
  "abstained": false,
  "citations": [
    {
      "artifact_id": "string",
      "source_url": "string",
      "artifact_type": "source_file | commit | pull_request | issue | document",
      "origin": "explicit | metadata-derived | inferred"
    }
  ]
}
```

**200 — abstained (insufficient evidence, FR-012)**
```json
{ "answer": "string explaining what's missing", "abstained": true, "citations": [] }
```

**Contract rules** (enforced by `answer_svc`, not just documented here):
- `citations` is never present-but-empty alongside a substantive claim — if `abstained: false`, at least one citation is required for every factual claim in `answer`.
- `origin: "inferred"` may only appear when no `explicit`/`metadata-derived` relationship exists for that piece of evidence (Constitution Principle II) — the response schema makes it impossible for the frontend to render an inferred citation identically to a deterministic one, since `origin` is always present and always checked before rendering.
- Every `citations[].source_url` MUST correspond to an artifact that was actually retrieved for this request (FR-013) — validated server-side before the response is returned, not left to the LLM's self-report.

## Error shape (all endpoints)

```json
{ "error": "string", "detail": "string | null" }
```
