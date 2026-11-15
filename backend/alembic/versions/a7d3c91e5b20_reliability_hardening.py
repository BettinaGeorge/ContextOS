"""reliability hardening: identity constraints, retry column, full-text search

Revision ID: a7d3c91e5b20
Revises: 4500f22c8686
Create Date: 2026-11-14

Order matters (specs/003-reliability-hardening/research.md §5): rows that would
violate a new constraint are cleaned up first, inside this one transaction.

Do not apply this revision to a database that holds data you care about before
rehearsing it on a copy (quickstart.md scenario 7). It deletes rows.

Until the US2 ingestion upsert and US4 idempotent enqueue are also deployed,
a second ingest or a second job for one connector will hit the new constraints
and fail, so ship this revision together with them.
"""

from typing import Sequence, Union

from alembic import op

revision: str = "a7d3c91e5b20"
down_revision: Union[str, Sequence[str], None] = "4500f22c8686"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

SEARCH_CONTENT_CHAR_LIMIT = 200000


def upgrade() -> None:
    # Legacy GitHub source files were keyed by blob SHA, which cannot be mapped to the
    # new path-based identity, and old versions would leave stale pieces. The next
    # ingest rebuilds them. Relationships and chunk children cascade.
    op.execute(
        "DELETE FROM artifacts WHERE source_system = 'github' AND artifact_type = 'source_file'"
    )

    # Keeper per identity is the newest ingested_at, ties broken by highest id.
    op.execute(
        """
        CREATE TEMP TABLE artifact_dedupe ON COMMIT DROP AS
        SELECT id AS duplicate_id, keeper_id
        FROM (
            SELECT id,
                   first_value(id) OVER (
                       PARTITION BY workspace_id, source_system, artifact_type, source_artifact_id
                       ORDER BY ingested_at DESC, id DESC
                   ) AS keeper_id
            FROM artifacts
        ) ranked
        WHERE id <> keeper_id
        """
    )
    op.execute(
        "UPDATE relationships r SET source_artifact_id = d.keeper_id "
        "FROM artifact_dedupe d WHERE r.source_artifact_id = d.duplicate_id"
    )
    op.execute(
        "UPDATE relationships r SET target_artifact_id = d.keeper_id "
        "FROM artifact_dedupe d WHERE r.target_artifact_id = d.duplicate_id"
    )
    op.execute(
        "UPDATE artifacts a SET parent_id = d.keeper_id "
        "FROM artifact_dedupe d WHERE a.parent_id = d.duplicate_id"
    )
    # An edge between two copies of the same artifact becomes a self-loop after repointing.
    op.execute(
        "DELETE FROM relationships WHERE source_artifact_id = target_artifact_id "
        "AND source_artifact_id IN (SELECT keeper_id FROM artifact_dedupe)"
    )
    op.execute("DELETE FROM artifacts WHERE id IN (SELECT duplicate_id FROM artifact_dedupe)")

    op.execute(
        """
        DELETE FROM relationships
        WHERE id IN (
            SELECT id FROM (
                SELECT id,
                       row_number() OVER (
                           PARTITION BY workspace_id, source_artifact_id, target_artifact_id,
                                        relationship_type
                           ORDER BY created_at, id
                       ) AS position
                FROM relationships
            ) ranked
            WHERE position > 1
        )
        """
    )

    op.execute(
        """
        UPDATE jobs
        SET status = 'failed',
            error_message = 'superseded by migration',
            completed_at = now()
        WHERE id IN (
            SELECT id FROM (
                SELECT id,
                       row_number() OVER (
                           PARTITION BY connector_id
                           ORDER BY (status = 'running') DESC, created_at DESC, id DESC
                       ) AS position
                FROM jobs
                WHERE status IN ('queued', 'running')
            ) ranked
            WHERE position > 1
        )
        """
    )

    op.create_unique_constraint(
        "uq_artifact_identity",
        "artifacts",
        ["workspace_id", "source_system", "artifact_type", "source_artifact_id"],
    )
    op.create_unique_constraint(
        "uq_relationship_edge",
        "relationships",
        ["workspace_id", "source_artifact_id", "target_artifact_id", "relationship_type"],
    )
    op.execute("ALTER TABLE jobs ADD COLUMN next_attempt_at timestamptz")
    op.execute(
        "CREATE UNIQUE INDEX uq_jobs_one_active_per_connector ON jobs (connector_id) "
        "WHERE status IN ('queued', 'running')"
    )
    op.execute(
        "ALTER TABLE artifacts ADD COLUMN search_vector tsvector GENERATED ALWAYS AS ("
        f"to_tsvector('english', title || ' ' || left(content, {SEARCH_CONTENT_CHAR_LIMIT}))"
        ") STORED"
    )
    op.execute("CREATE INDEX ix_artifacts_search_vector ON artifacts USING gin (search_vector)")


def downgrade() -> None:
    # Rows deleted by upgrade() (duplicates, legacy GitHub source files, surplus
    # relationships) are not restored; superseded jobs stay 'failed'.
    op.execute("DROP INDEX IF EXISTS ix_artifacts_search_vector")
    op.execute("ALTER TABLE artifacts DROP COLUMN IF EXISTS search_vector")
    op.execute("DROP INDEX IF EXISTS uq_jobs_one_active_per_connector")
    op.execute("ALTER TABLE jobs DROP COLUMN IF EXISTS next_attempt_at")
    op.drop_constraint("uq_relationship_edge", "relationships", type_="unique")
    op.drop_constraint("uq_artifact_identity", "artifacts", type_="unique")
