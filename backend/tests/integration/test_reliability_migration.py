"""Migration a7d3c91e5b20 against a dedicated scratch database.

Runs only when MIGRATION_TEST_DATABASE_URL points at a database whose name ends in
`_migration_test` (for example `createdb -p 5433 contextos_migration_test`). The
database is wiped and rebuilt on every run, so it must never hold data you care about.
Your dev database is never touched.
"""

import os
import subprocess
import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlparse

import asyncpg
import pytest

SCRATCH_URL = os.environ.get("MIGRATION_TEST_DATABASE_URL", "")
BACKEND_DIR = Path(__file__).resolve().parents[2]
BASE_REVISION = "4500f22c8686"

pytestmark = pytest.mark.skipif(
    not urlparse(SCRATCH_URL).path.endswith("_migration_test"),
    reason="set MIGRATION_TEST_DATABASE_URL to a database named *_migration_test",
)


def _alembic(*args: str) -> None:
    result = subprocess.run(
        [sys.executable, "-m", "alembic", *args],
        cwd=BACKEND_DIR,
        env={**os.environ, "DATABASE_URL": SCRATCH_URL},
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr


async def _connect() -> asyncpg.Connection:
    return await asyncpg.connect(SCRATCH_URL.replace("postgresql+asyncpg://", "postgresql://"))


async def _reset_to_base_revision() -> None:
    connection = await _connect()
    try:
        await connection.execute("DROP SCHEMA public CASCADE; CREATE SCHEMA public")
        await connection.execute("CREATE EXTENSION IF NOT EXISTS vector")
    finally:
        await connection.close()
    _alembic("upgrade", BASE_REVISION)


async def _insert_artifact(
    connection, workspace_id, source_system, artifact_type, source_artifact_id, ingested_at,
    content="body",
) -> uuid.UUID:
    artifact_id = uuid.uuid4()
    await connection.execute(
        "INSERT INTO artifacts (id, workspace_id, source_system, artifact_type, "
        "source_artifact_id, title, content, source_url, ingestion_version, ingested_at) "
        "VALUES ($1, $2, $3::artifact_source_system, $4::artifact_type, $5, $6, $7, $8, 1, $9)",
        artifact_id, workspace_id, source_system, artifact_type, source_artifact_id,
        f"title {source_artifact_id}", content, f"https://example.test/{source_artifact_id}",
        ingested_at,
    )
    return artifact_id


async def _insert_relationship(connection, workspace_id, source_id, target_id, kind) -> None:
    await connection.execute(
        "INSERT INTO relationships (id, workspace_id, source_artifact_id, target_artifact_id, "
        "relationship_type, relationship_origin) VALUES ($1, $2, $3, $4, $5, 'explicit')",
        uuid.uuid4(), workspace_id, source_id, target_id, kind,
    )


async def _insert_job(connection, workspace_id, connector_id, status, created_at) -> uuid.UUID:
    job_id = uuid.uuid4()
    await connection.execute(
        "INSERT INTO jobs (id, workspace_id, connector_id, job_type, status, attempts, created_at) "
        "VALUES ($1, $2, $3, 'ingest_github', $4::job_status, 0, $5)",
        job_id, workspace_id, connector_id, status, created_at,
    )
    return job_id


@pytest.fixture
async def seeded() -> dict:
    await _reset_to_base_revision()
    now = datetime.now(timezone.utc)
    older, newer = now - timedelta(hours=2), now - timedelta(hours=1)
    ids: dict = {}
    connection = await _connect()
    try:
        workspace_id = uuid.uuid4()
        connector_id = uuid.uuid4()
        await connection.execute(
            "INSERT INTO workspaces (id, owner_user_id, name) VALUES ($1, 'owner', 'ws')",
            workspace_id,
        )
        await connection.execute(
            "INSERT INTO connectors (id, workspace_id, source_system, status, "
            "encrypted_access_token, external_resource_ref) "
            "VALUES ($1, $2, 'github', 'connected', 'token', 'owner/repo')",
            connector_id, workspace_id,
        )
        ids.update(workspace=workspace_id, connector=connector_id)

        async def link(source, target, kind):
            await _insert_relationship(connection, workspace_id, source, target, kind)

        async def add_job(status, created_at):
            return await _insert_job(connection, workspace_id, connector_id, status, created_at)

        ids["page_old"] = await _insert_artifact(
            connection, workspace_id, "notion", "document", "page-1", older
        )
        ids["page_new"] = await _insert_artifact(
            connection, workspace_id, "notion", "document", "page-1", newer, content="alpha beta"
        )
        ids["target"] = await _insert_artifact(
            connection, workspace_id, "github", "pull_request", "42", newer
        )
        ids["other"] = await _insert_artifact(
            connection, workspace_id, "github", "pull_request", "43", newer
        )
        ids["legacy_file"] = await _insert_artifact(
            connection, workspace_id, "github", "source_file", "blobsha123", newer
        )
        ids["commit"] = await _insert_artifact(
            connection, workspace_id, "github", "commit", "commitsha", newer
        )

        await link(ids["page_old"], ids["target"], "documents")
        await link(ids["page_new"], ids["target"], "documents")
        await link(ids["other"], ids["target"], "mentions")
        await link(ids["other"], ids["target"], "mentions")
        await link(ids["legacy_file"], ids["target"], "implements")

        ids["job_running"] = await add_job("running", older)
        ids["job_queued"] = await add_job("queued", newer)
    finally:
        await connection.close()
    _alembic("upgrade", "head")
    return ids


async def _fetch(query: str, *args):
    connection = await _connect()
    try:
        return await connection.fetch(query, *args)
    finally:
        await connection.close()


async def test_duplicate_artifacts_collapse_to_newest_with_relationships_repointed(seeded):
    rows = await _fetch(
        "SELECT id FROM artifacts WHERE source_artifact_id = 'page-1' AND workspace_id = $1",
        seeded["workspace"],
    )
    assert [row["id"] for row in rows] == [seeded["page_new"]]

    edges = await _fetch(
        "SELECT source_artifact_id FROM relationships "
        "WHERE target_artifact_id = $1 AND relationship_type = 'documents'",
        seeded["target"],
    )
    assert [row["source_artifact_id"] for row in edges] == [seeded["page_new"]]


async def test_duplicate_relationships_collapse_to_one(seeded):
    rows = await _fetch(
        "SELECT id FROM relationships "
        "WHERE source_artifact_id = $1 AND relationship_type = 'mentions'",
        seeded["other"],
    )
    assert len(rows) == 1


async def test_legacy_github_source_files_and_their_relationships_are_removed(seeded):
    files = await _fetch("SELECT id FROM artifacts WHERE artifact_type = 'source_file'")
    assert files == []
    edges = await _fetch(
        "SELECT id FROM relationships WHERE relationship_type = 'implements'"
    )
    assert edges == []
    commits = await _fetch("SELECT id FROM artifacts WHERE artifact_type = 'commit'")
    assert len(commits) == 1


async def test_one_active_job_per_connector_and_surplus_is_marked_failed(seeded):
    active = await _fetch(
        "SELECT id FROM jobs WHERE connector_id = $1 AND status IN ('queued', 'running')",
        seeded["connector"],
    )
    assert [row["id"] for row in active] == [seeded["job_running"]]

    superseded = await _fetch(
        "SELECT status::text AS status, error_message FROM jobs WHERE id = $1",
        seeded["job_queued"],
    )
    assert superseded[0]["status"] == "failed"
    assert superseded[0]["error_message"] == "superseded by migration"


async def test_new_schema_objects_exist(seeded):
    constraints = {
        row["conname"]
        for row in await _fetch(
            "SELECT conname FROM pg_constraint "
            "WHERE conname IN ('uq_artifact_identity', 'uq_relationship_edge')"
        )
    }
    assert constraints == {"uq_artifact_identity", "uq_relationship_edge"}

    indexes = {row["indexname"] for row in await _fetch("SELECT indexname FROM pg_indexes")}
    assert {"uq_jobs_one_active_per_connector", "ix_artifacts_search_vector"} <= indexes

    columns = {
        row["column_name"]
        for row in await _fetch(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_name IN ('jobs', 'artifacts')"
        )
    }
    assert {"next_attempt_at", "search_vector"} <= columns


async def test_search_vector_is_generated_from_title_and_content(seeded):
    rows = await _fetch(
        "SELECT id FROM artifacts WHERE search_vector @@ to_tsquery('english', 'alpha')"
    )
    assert [row["id"] for row in rows] == [seeded["page_new"]]


async def test_new_constraints_reject_duplicates(seeded):
    connection = await _connect()
    try:
        with pytest.raises(asyncpg.UniqueViolationError):
            await _insert_artifact(
                connection, seeded["workspace"], "notion", "document", "page-1",
                datetime.now(timezone.utc),
            )
        with pytest.raises(asyncpg.UniqueViolationError):
            await _insert_job(
                connection, seeded["workspace"], seeded["connector"], "queued",
                datetime.now(timezone.utc),
            )
    finally:
        await connection.close()


async def test_downgrade_then_upgrade_round_trips(seeded):
    _alembic("downgrade", BASE_REVISION)
    _alembic("upgrade", "head")
