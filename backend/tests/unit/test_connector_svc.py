import base64

import httpx
import pytest
import respx

from src.models.artifact import EMBEDDING_DIM, ArtifactType, SourceSystem
from src.models.workspace import Workspace
from src.repositories.artifact_repository import ArtifactRepository
from src.repositories.connector_repository import ConnectorRepository
from src.services.connector_svc import ConnectorService


class FakeVoyageClient:
    """Avoids a real Voyage API call — returns deterministic fake vectors of
    the right dimensionality so we can verify the orchestration logic
    (chunking -> embedding -> persistence) without live credentials. Mirrors
    the real Voyage API's behavior of rejecting a batch containing any empty
    string (found by running ingestion against a real repo with empty
    __init__.py files — T061 quickstart validation), so this fake would also
    fail the way production did if that guard regresses."""

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        if any(not t.strip() for t in texts):
            raise ValueError("Voyage rejects batches containing empty strings")
        return [[0.1] * EMBEDDING_DIM for _ in texts]


@pytest.mark.asyncio
@respx.mock
async def test_ingest_github_persists_chunked_and_embedded_artifacts(db_session):
    workspace = Workspace(owner_user_id="test-user", name="Test")
    db_session.add(workspace)
    await db_session.commit()
    await db_session.refresh(workspace)

    connector = await ConnectorRepository(db_session).create(
        workspace_id=workspace.id,
        source_system=SourceSystem.github,
        raw_access_token="fake-token",
        external_resource_ref="acme/widgets",
    )

    respx.get("https://api.github.com/repos/acme/widgets").mock(
        return_value=httpx.Response(200, json={"default_branch": "main"})
    )
    respx.get("https://api.github.com/repos/acme/widgets/git/trees/main").mock(
        return_value=httpx.Response(
            200, json={"tree": [{"type": "blob", "path": "app.py", "sha": "sha1"}]}
        )
    )
    py_source = "def foo():\n    return 1\n\n\ndef bar():\n    return 2\n"
    respx.get("https://api.github.com/repos/acme/widgets/contents/app.py").mock(
        return_value=httpx.Response(
            200,
            json={"encoding": "base64", "content": base64.b64encode(py_source.encode()).decode()},
        )
    )
    respx.get("https://api.github.com/repos/acme/widgets/pulls").mock(
        return_value=httpx.Response(200, json=[])
    )
    respx.get("https://api.github.com/repos/acme/widgets/commits").mock(
        return_value=httpx.Response(200, json=[])
    )
    respx.get("https://api.github.com/repos/acme/widgets/issues").mock(
        return_value=httpx.Response(200, json=[])
    )

    svc = ConnectorService(db_session, voyage_client=FakeVoyageClient())
    count = await svc.ingest(workspace.id, connector)

    # app.py has 2 top-level functions -> chunked into 2 separate rows.
    assert count == 2

    rows = await ArtifactRepository(db_session).list_by_workspace(
        workspace.id, artifact_type=ArtifactType.source_file
    )
    assert len(rows) == 2
    titles = {r.title for r in rows}
    assert any("foo" in t for t in titles)
    assert any("bar" in t for t in titles)
    assert all(r.embedding is not None for r in rows)
    assert all(len(r.embedding) == EMBEDDING_DIM for r in rows)
    assert all(r.source_url.startswith("https://github.com/acme/widgets") for r in rows)


@pytest.mark.asyncio
@respx.mock
async def test_ingest_skips_empty_files_instead_of_failing_the_whole_batch(db_session):
    """Real repos contain empty files (e.g. `__init__.py` package markers,
    found ingesting a real repo during T061 quickstart validation). Voyage's
    embed API rejects a batch containing any empty string, so a naive
    embed-everything call would fail ingestion entirely over one blank file."""
    workspace = Workspace(owner_user_id="test-user", name="Test")
    db_session.add(workspace)
    await db_session.commit()
    await db_session.refresh(workspace)

    connector = await ConnectorRepository(db_session).create(
        workspace_id=workspace.id,
        source_system=SourceSystem.github,
        raw_access_token="fake-token",
        external_resource_ref="acme/widgets",
    )

    respx.get("https://api.github.com/repos/acme/widgets").mock(
        return_value=httpx.Response(200, json={"default_branch": "main"})
    )
    respx.get("https://api.github.com/repos/acme/widgets/git/trees/main").mock(
        return_value=httpx.Response(
            200,
            json={
                "tree": [
                    {"type": "blob", "path": "app.py", "sha": "sha1"},
                    {"type": "blob", "path": "__init__.py", "sha": "sha2"},
                ]
            },
        )
    )
    py_source = "def foo():\n    return 1\n"
    respx.get("https://api.github.com/repos/acme/widgets/contents/app.py").mock(
        return_value=httpx.Response(
            200,
            json={"encoding": "base64", "content": base64.b64encode(py_source.encode()).decode()},
        )
    )
    respx.get("https://api.github.com/repos/acme/widgets/contents/__init__.py").mock(
        return_value=httpx.Response(
            200, json={"encoding": "base64", "content": base64.b64encode(b"").decode()}
        )
    )
    respx.get("https://api.github.com/repos/acme/widgets/pulls").mock(
        return_value=httpx.Response(200, json=[])
    )
    respx.get("https://api.github.com/repos/acme/widgets/commits").mock(
        return_value=httpx.Response(200, json=[])
    )
    respx.get("https://api.github.com/repos/acme/widgets/issues").mock(
        return_value=httpx.Response(200, json=[])
    )

    svc = ConnectorService(db_session, voyage_client=FakeVoyageClient())
    count = await svc.ingest(workspace.id, connector)

    assert count == 1
    rows = await ArtifactRepository(db_session).list_by_workspace(
        workspace.id, artifact_type=ArtifactType.source_file
    )
    assert len(rows) == 1
    assert rows[0].title == "app.py"
