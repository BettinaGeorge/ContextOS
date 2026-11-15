# ADR-007: Job retry, safe claiming, and one active job per connector

Status: Accepted (2026-11-15; validated in `specs/003-reliability-hardening/validation.md`).

## Context

ADR-001 accepted a Postgres jobs table with "no built-in retry/backoff, worker concurrency, or dead-letter handling." Claiming is a select followed by an update, so two workers could take the same job. A failed job is never retried, and the connector is marked failed on the first error. Adding a value to a PostgreSQL enum needs extra migration handling, and feature 002 (parked) will also migrate the connector table.

## Decision

- **Retry as a queued job**: on a transient failure with attempts remaining, the job returns to `queued` with a future `next_attempt_at`. No new enum values. Delays are `(30, 120)` seconds, so three attempts in total. Credential rejections and a missing connector are permanent and not retried.
- **Connector status**: stays `ingesting` while retries remain; `failed` only after the final attempt.
- **Claiming**: one `SELECT ... FOR UPDATE SKIP LOCKED` honouring `next_attempt_at`, with the status update in the same transaction.
- **One active job per connector**: partial unique index on `jobs (connector_id)` for `queued` and `running`; a second trigger returns the existing job.
- **Abandoned jobs**: at enqueue, a job `running` for more than 60 minutes is marked failed ("abandoned: worker stopped") before inserting.

## Consequences

- No enum migration, so no conflict with feature 002's connector changes.
- Multiple workers can run safely, each job once.
- The abandoned-job sweep is a minimal guard, not general crash recovery. A healthy job that runs longer than 60 minutes could be swept and overlapped by a second run; this is harmless because ingestion is idempotent (ADR-005).
- Retry must not ship before idempotent ingestion.
- Retries sit on top of the embedding client's own rate-limit retry, which is kept.

## Alternatives considered

- **A `retrying` enum value on jobs and connectors**: migration cost and a conflict with feature 002.
- **Sleeping inside the handler**: holds the worker and loses the retry on restart.
- **Application-level check for a duplicate active job**: racy.
- **Reset all running jobs at process start**: unsafe once more than one instance runs.
- **Lease and heartbeat system**: out of scope for this feature.
- **Redis/Celery/RQ**: rejected in ADR-001 and still outside the constitution's constraints.
