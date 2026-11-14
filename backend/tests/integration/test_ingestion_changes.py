"""SC-002 and the edge cases of FR-005 to FR-009 (specs/003)."""

import pytest
from _ingestion_support import (
    ONE_FUNCTION,
    THREE_FUNCTIONS,
    TWO_FUNCTIONS,
    CountingVoyage,
    make_workspace,
    snapshot,
    source_file,
    stored_artifacts,
)

from src.models.artifact import SourceSystem
from src.services.connector_svc import ConnectorService


async def _ingest(db_session, workspace, voyage, files: dict[str, str]) -> None:
    await ConnectorService(db_session, voyage_client=voyage).ingest_normalized(
        workspace.id,
        SourceSystem.github,
        [source_file(path, content) for path, content in files.items()],
    )


def _ids_for(artifacts, path: str) -> set[str]:
    return {a.source_artifact_id for a in artifacts if a.title.startswith(path)}


@pytest.mark.asyncio
async def test_changing_one_file_re_embeds_only_that_file_and_leaves_no_old_version(db_session):
    workspace = await make_workspace(db_session)
    voyage = CountingVoyage()
    await _ingest(db_session, workspace, voyage, {"a.py": TWO_FUNCTIONS, "b.py": ONE_FUNCTION})
    batches_before = len(voyage.batches)

    changed = "def foo():\n    return 'changed'\n"
    await _ingest(db_session, workspace, voyage, {"a.py": TWO_FUNCTIONS, "b.py": changed})

    new_texts = [t for batch in voyage.batches[batches_before:] for t in batch]
    assert new_texts == [changed]
    artifacts = await stored_artifacts(db_session, workspace.id)
    by_path = {a.source_artifact_id: a for a in artifacts}
    assert by_path["b.py"].content == changed
    assert by_path["b.py"].ingestion_version == 2
    assert all(a.ingestion_version == 1 for a in artifacts if a.title.startswith("a.py"))
    assert not any(a.content == ONE_FUNCTION for a in artifacts)


@pytest.mark.asyncio
async def test_file_that_shrinks_leaves_no_leftover_pieces(db_session):
    workspace = await make_workspace(db_session)
    voyage = CountingVoyage()
    await _ingest(db_session, workspace, voyage, {"a.py": THREE_FUNCTIONS})
    assert _ids_for(await stored_artifacts(db_session, workspace.id), "a.py") == {
        "a.py#chunk0",
        "a.py#chunk1",
        "a.py#chunk2",
    }

    await _ingest(db_session, workspace, voyage, {"a.py": TWO_FUNCTIONS})

    assert _ids_for(await stored_artifacts(db_session, workspace.id), "a.py") == {
        "a.py#chunk0",
        "a.py#chunk1",
    }


@pytest.mark.asyncio
async def test_file_flipping_between_one_piece_and_many_leaves_no_stale_row(db_session):
    workspace = await make_workspace(db_session)
    voyage = CountingVoyage()

    await _ingest(db_session, workspace, voyage, {"a.py": TWO_FUNCTIONS})
    await _ingest(db_session, workspace, voyage, {"a.py": ONE_FUNCTION})
    assert _ids_for(await stored_artifacts(db_session, workspace.id), "a.py") == {"a.py"}

    await _ingest(db_session, workspace, voyage, {"a.py": TWO_FUNCTIONS})
    assert _ids_for(await stored_artifacts(db_session, workspace.id), "a.py") == {
        "a.py#chunk0",
        "a.py#chunk1",
    }


@pytest.mark.asyncio
async def test_file_that_becomes_empty_loses_all_its_pieces(db_session):
    workspace = await make_workspace(db_session)
    voyage = CountingVoyage()
    await _ingest(db_session, workspace, voyage, {"a.py": TWO_FUNCTIONS})

    await _ingest(db_session, workspace, voyage, {"a.py": ""})

    assert await stored_artifacts(db_session, workspace.id) == []


@pytest.mark.asyncio
async def test_failed_run_then_rerun_ends_identical_to_one_clean_run(db_session):
    files = {"a.py": TWO_FUNCTIONS, "b.py": ONE_FUNCTION}
    clean_workspace = await make_workspace(db_session)
    await _ingest(db_session, clean_workspace, CountingVoyage(), files)
    expected = snapshot(await stored_artifacts(db_session, clean_workspace.id))

    workspace = await make_workspace(db_session)
    with pytest.raises(RuntimeError):
        await _ingest(db_session, workspace, CountingVoyage(fail_next_call=True), files)
    assert await stored_artifacts(db_session, workspace.id) == []

    await _ingest(db_session, workspace, CountingVoyage(), files)

    assert snapshot(await stored_artifacts(db_session, workspace.id)) == expected


@pytest.mark.asyncio
async def test_reingesting_one_workspace_leaves_another_untouched(db_session):
    workspace_a = await make_workspace(db_session)
    workspace_b = await make_workspace(db_session)
    voyage = CountingVoyage()
    files = {"a.py": TWO_FUNCTIONS, "b.py": ONE_FUNCTION}
    await _ingest(db_session, workspace_a, voyage, files)
    await _ingest(db_session, workspace_b, voyage, files)
    before = snapshot(await stored_artifacts(db_session, workspace_b.id))

    await _ingest(db_session, workspace_a, voyage, {"a.py": ONE_FUNCTION})

    after_artifacts = await stored_artifacts(db_session, workspace_b.id)
    assert snapshot(after_artifacts) == before
    assert all(a.ingestion_version == 1 for a in after_artifacts)


@pytest.mark.asyncio
async def test_two_files_with_identical_content_stay_two_artifacts(db_session):
    workspace = await make_workspace(db_session)
    voyage = CountingVoyage()

    await _ingest(db_session, workspace, voyage, {"a.py": ONE_FUNCTION, "b.py": ONE_FUNCTION})

    artifacts = await stored_artifacts(db_session, workspace.id)
    assert {a.source_artifact_id for a in artifacts} == {"a.py", "b.py"}
    assert len(voyage.embedded_texts) == 2


@pytest.mark.asyncio
async def test_renamed_title_updates_in_place_without_re_embedding(db_session):
    workspace = await make_workspace(db_session)
    voyage = CountingVoyage()
    await _ingest(db_session, workspace, voyage, {"a.py": ONE_FUNCTION})
    embedded_before = len(voyage.embedded_texts)
    original = (await stored_artifacts(db_session, workspace.id))[0]

    moved = source_file("a.py", ONE_FUNCTION)
    moved.source_url = "https://github.com/acme/widgets/blob/main/a.py"
    await ConnectorService(db_session, voyage_client=voyage).ingest_normalized(
        workspace.id, SourceSystem.github, [moved]
    )

    updated = (await stored_artifacts(db_session, workspace.id))[0]
    assert updated.id == original.id
    assert updated.source_url.endswith("/blob/main/a.py")
    assert updated.ingestion_version == 1
    assert len(voyage.embedded_texts) == embedded_before
