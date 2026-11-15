"""FR-005 to FR-008 (specs/003): deciding what to embed and what to leave alone."""

import hashlib

from src.models.artifact import Artifact, ArtifactType, SourceSystem
from src.services.connector_svc import ExistingPiece, partition_rows


def _checksum(content: str) -> str:
    return hashlib.sha256(content.encode()).hexdigest()


def _row(
    source_artifact_id="a.py",
    content="body",
    title="a.py",
    source_url="https://github.com/acme/widgets/blob/HEAD/a.py",
    artifact_type=ArtifactType.source_file,
) -> Artifact:
    return Artifact(
        source_system=SourceSystem.github,
        source_artifact_id=source_artifact_id,
        artifact_type=artifact_type,
        title=title,
        content=content,
        source_url=source_url,
        checksum=_checksum(content),
    )


def _existing(row: Artifact, **overrides) -> ExistingPiece:
    fields = {
        "checksum": row.checksum,
        "title": row.title,
        "source_url": row.source_url,
        "has_embedding": True,
    }
    fields.update(overrides)
    return ExistingPiece(**fields)


def _key(row: Artifact) -> tuple[ArtifactType, str]:
    return (ArtifactType(row.artifact_type), row.source_artifact_id)


def test_row_missing_from_storage_is_new():
    row = _row()

    result = partition_rows([row], {})

    assert result.new == [row]
    assert result.content_changed == [] and result.metadata_changed == []
    assert result.unchanged == []


def test_same_content_and_same_metadata_is_unchanged():
    row = _row()

    result = partition_rows([row], {_key(row): _existing(row)})

    assert result.unchanged == [row]
    assert result.new == [] and result.content_changed == [] and result.metadata_changed == []


def test_same_content_but_different_title_is_metadata_only():
    row = _row(title="renamed.py")
    stored = _existing(row, title="a.py")

    result = partition_rows([row], {_key(row): stored})

    assert result.metadata_changed == [row]
    assert result.content_changed == []


def test_same_content_but_different_source_url_is_metadata_only():
    row = _row(source_url="https://github.com/acme/widgets/blob/HEAD/moved.py")
    stored = _existing(row, source_url="https://github.com/acme/widgets/blob/HEAD/a.py")

    result = partition_rows([row], {_key(row): stored})

    assert result.metadata_changed == [row]


def test_different_content_is_content_changed():
    row = _row(content="new body")
    stored = _existing(row, checksum=_checksum("old body"))

    result = partition_rows([row], {_key(row): stored})

    assert result.content_changed == [row]
    assert result.metadata_changed == []


def test_missing_embedding_forces_re_embed_even_when_checksum_matches():
    row = _row()

    result = partition_rows([row], {_key(row): _existing(row, has_embedding=False)})

    assert result.content_changed == [row]


def test_stored_row_without_checksum_is_treated_as_content_changed():
    row = _row()

    result = partition_rows([row], {_key(row): _existing(row, checksum=None)})

    assert result.content_changed == [row]


def test_identical_content_at_two_paths_stays_two_rows():
    first = _row(source_artifact_id="a.py", title="a.py")
    second = _row(source_artifact_id="b.py", title="b.py")

    result = partition_rows([first, second], {})

    assert result.new == [first, second]


def test_same_source_artifact_id_under_different_types_is_not_confused():
    pull_request = _row(source_artifact_id="1", artifact_type=ArtifactType.pull_request)
    issue = _row(source_artifact_id="1", artifact_type=ArtifactType.issue)
    existing = {_key(pull_request): _existing(pull_request)}

    result = partition_rows([pull_request, issue], existing)

    assert result.unchanged == [pull_request]
    assert result.new == [issue]
