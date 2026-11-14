import base64

import httpx
import pytest
import respx

from src.connectors.base import ConnectorAuthError
from src.connectors.github_connector import GitHubConnector


@pytest.fixture
def connector():
    return GitHubConnector(access_token="fake-token", owner="acme", repo="widgets")


@pytest.mark.asyncio
@respx.mock
async def test_authenticate_succeeds_on_200(connector):
    respx.get("https://api.github.com/repos/acme/widgets").mock(
        return_value=httpx.Response(200, json={"default_branch": "main"})
    )
    await connector.authenticate()  # should not raise


@pytest.mark.asyncio
@respx.mock
async def test_authenticate_raises_on_404(connector):
    respx.get("https://api.github.com/repos/acme/widgets").mock(return_value=httpx.Response(404))
    with pytest.raises(httpx.HTTPStatusError):
        await connector.authenticate()


@pytest.mark.asyncio
@respx.mock
async def test_authenticate_raises_connector_auth_error_on_401(connector):
    respx.get("https://api.github.com/repos/acme/widgets").mock(return_value=httpx.Response(401))
    with pytest.raises(ConnectorAuthError):
        await connector.authenticate()


@pytest.mark.asyncio
@respx.mock
async def test_authenticate_raises_connector_auth_error_on_403(connector):
    respx.get("https://api.github.com/repos/acme/widgets").mock(return_value=httpx.Response(403))
    with pytest.raises(ConnectorAuthError):
        await connector.authenticate()


@pytest.mark.asyncio
@respx.mock
async def test_ingest_full_normalizes_files_prs_commits_issues(connector):
    respx.get("https://api.github.com/repos/acme/widgets").mock(
        return_value=httpx.Response(200, json={"default_branch": "main"})
    )
    respx.get("https://api.github.com/repos/acme/widgets/git/trees/main").mock(
        return_value=httpx.Response(
            200,
            json={"tree": [{"type": "blob", "path": "README.md", "sha": "abc123"}]},
        )
    )
    encoded = base64.b64encode(b"# Widgets\nA widget factory.").decode()
    respx.get("https://api.github.com/repos/acme/widgets/contents/README.md").mock(
        return_value=httpx.Response(200, json={"encoding": "base64", "content": encoded})
    )
    respx.get("https://api.github.com/repos/acme/widgets/pulls").mock(
        return_value=httpx.Response(
            200,
            json=[
                {
                    "number": 1,
                    "title": "Add widget spinner",
                    "body": "Implements spinner.",
                    "html_url": "https://github.com/acme/widgets/pull/1",
                    "user": {"login": "octocat"},
                    "created_at": "2026-01-01T00:00:00Z",
                    "updated_at": "2026-01-02T00:00:00Z",
                    "state": "closed",
                    "merged_at": "2026-01-02T00:00:00Z",
                }
            ],
        )
    )
    respx.get("https://api.github.com/repos/acme/widgets/commits").mock(
        return_value=httpx.Response(
            200,
            json=[
                {
                    "sha": "deadbeef",
                    "html_url": "https://github.com/acme/widgets/commit/deadbeef",
                    "commit": {
                        "message": "Add spinner\n\nDetails here.",
                        "author": {"name": "Octo Cat", "date": "2026-01-02T00:00:00Z"},
                    },
                }
            ],
        )
    )
    respx.get("https://api.github.com/repos/acme/widgets/issues").mock(
        return_value=httpx.Response(
            200,
            json=[
                {
                    "number": 2,
                    "title": "Spinner is too fast",
                    "body": "Please slow it down.",
                    "html_url": "https://github.com/acme/widgets/issues/2",
                    "user": {"login": "octocat"},
                    "created_at": "2026-01-03T00:00:00Z",
                    "updated_at": "2026-01-03T00:00:00Z",
                    "state": "open",
                },
                {
                    # PRs also appear in /issues — must be filtered out.
                    "number": 1,
                    "title": "Add widget spinner",
                    "pull_request": {"url": "..."},
                    "state": "closed",
                },
            ],
        )
    )

    artifacts = await connector.ingest_full()
    by_type = {}
    for a in artifacts:
        by_type.setdefault(a.artifact_type, []).append(a)

    assert len(by_type["source_file"]) == 1
    assert by_type["source_file"][0].content == "# Widgets\nA widget factory."
    assert by_type["source_file"][0].source_url.endswith("/blob/HEAD/README.md")

    assert len(by_type["pull_request"]) == 1
    assert by_type["pull_request"][0].title == "Add widget spinner"

    assert len(by_type["commit"]) == 1
    assert by_type["commit"][0].title == "Add spinner"

    # Only the real issue, not the PR that /issues also returned.
    assert len(by_type["issue"]) == 1
    assert by_type["issue"][0].title == "Spinner is too fast"


def test_source_file_identity_is_its_path_and_distinct_for_identical_blobs(connector):
    first = connector.normalize_artifact(
        {"type": "file", "path": "src/a.py", "content": "same", "sha": "blob-sha"}
    )
    second = connector.normalize_artifact(
        {"type": "file", "path": "src/b.py", "content": "same", "sha": "blob-sha"}
    )

    assert first.source_artifact_id == "src/a.py"
    assert second.source_artifact_id == "src/b.py"
    assert first.source_artifact_id != second.source_artifact_id
