# API Contract Changes: Phase 1 Reliability Hardening

Only differences from `specs/001-trace-doc-to-code/contracts/api.md` are listed. Every change is additive: existing fields keep their names, types and meaning, so current clients keep working. `POST /ask` is unchanged (citation validation and abstention are explicitly out of scope).

## `POST /ingest/{connector_id}`

**Behavior change**: idempotent. If the connector already has a queued, running or waiting-to-retry job, no new job is created and the response describes the existing one.

**202** (same shape as before, plus new fields):
```json
{
  "job_id": "string",
  "status": "queued | running | complete | failed",
  "error_message": "string | null",
  "attempts": 0,
  "max_attempts": 3,
  "next_attempt_at": "iso8601 | null"
}
```

If a `running` job for this connector has been running for more than 60 minutes, it is first marked `failed` ("abandoned: worker stopped") and a new job is created.

## `GET /ingest/{job_id}/status`

**200**: same shape as above. A job waiting to retry has `status: "queued"`, `attempts > 0` and a future `next_attempt_at`. After the final failed attempt: `status: "failed"`, `attempts == max_attempts`, and `error_message` holds the last error.

## `GET /connectors` and `GET /connectors/{connector_id}/status`

**200** (existing fields unchanged, three new nullable fields taken from the connector's most recent job):
```json
{
  "connector_id": "string",
  "source_system": "github | notion",
  "status": "connected | ingesting | complete | failed | needs_reconnect",
  "last_ingested_at": "iso8601 | null",
  "error_message": "string | null",
  "ingestion_attempts": "integer | null",
  "max_attempts": "integer | null",
  "next_attempt_at": "iso8601 | null"
}
```

- While retries remain: `status: "ingesting"`, `ingestion_attempts > 0`, `next_attempt_at` set to the retry time (or null while an attempt is running), and `error_message` holds the latest attempt's error.
- After the final failed attempt: `status: "failed"`, `ingestion_attempts == max_attempts`, `error_message` holds the last error.
- Credential rejection: `status: "needs_reconnect"`, `ingestion_attempts == 1`. Not retried.
- All three new fields are `null` for a connector that has never had a job.

## Frontend contract (status page)

- `ConnectorStatusResponse` and `IngestJobResponse` in `frontend/src/lib/api.ts` gain the optional fields above.
- When `status === "ingesting"` and `ingestion_attempts > 0`, the page shows "Retrying (attempt N of M)" and renders `error_message` in a muted style, not the failure style.
- When `status === "failed"`, the page shows the attempt count and `error_message` in the failure style.
- `TERMINAL_STATUSES` is unchanged (`complete`, `failed`, `needs_reconnect`), so polling continues through retries.

## Internal contract: evidence block (not an HTTP endpoint)

The text sent to the model keeps the same structure: one `<evidence>` section containing one `<item>` per retrieved artifact with `artifact_id`, `type`, `origin` and `source_url` attributes. Every attribute value and every item body is HTML-escaped. The fixed system prompt gains one sentence explaining the escaping. The `[cite:ARTIFACT_ID]` citation format is unchanged.
