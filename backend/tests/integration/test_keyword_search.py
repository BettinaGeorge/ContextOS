"""FR-011 to FR-013 (specs/003): ranked full-text keyword search over the stored
search_vector column. Needs a migrated database (alembic upgrade head)."""

import pytest

from src.models.artifact import Artifact, ArtifactType, SourceSystem
from src.models.workspace import Workspace
from src.repositories.artifact_repository import ArtifactRepository


async def _workspace(db_session, owner: str) -> Workspace:
    workspace = Workspace(owner_user_id=owner, name="Search test")
    db_session.add(workspace)
    await db_session.commit()
    await db_session.refresh(workspace)
    return workspace


async def _add(db_session, workspace, source_id: str, title: str, content: str) -> Artifact:
    artifact = Artifact(
        workspace_id=workspace.id,
        source_system=SourceSystem.github,
        source_artifact_id=source_id,
        artifact_type=ArtifactType.source_file,
        title=title,
        content=content,
        source_url=f"https://github.com/acme/widgets/blob/HEAD/{source_id}",
    )
    db_session.add(artifact)
    await db_session.commit()
    await db_session.refresh(artifact)
    return artifact


@pytest.mark.asyncio
async def test_question_terms_in_different_sentences_still_match(db_session):
    workspace = await _workspace(db_session, "kw-different-sentences")
    target = await _add(
        db_session,
        workspace,
        "auth.py",
        "auth.py",
        "The login form posts credentials. Separately, a failed call is retried three times.",
    )
    await _add(db_session, workspace, "other.py", "other.py", "Unrelated billing code.")

    results = await ArtifactRepository(db_session).search_fulltext(
        workspace.id, "how does the login retry work"
    )

    assert [a.id for a in results] == [target.id]


@pytest.mark.asyncio
async def test_results_are_ordered_by_relevance(db_session):
    workspace = await _workspace(db_session, "kw-ranking")
    weak = await _add(db_session, workspace, "weak.py", "weak.py", "Mentions login once.")
    strong = await _add(
        db_session,
        workspace,
        "strong.py",
        "strong.py",
        "login retry login retry login retry: the login retry policy.",
    )

    results = await ArtifactRepository(db_session).search_fulltext(workspace.id, "login retry")

    assert [a.id for a in results] == [strong.id, weak.id]


@pytest.mark.asyncio
async def test_results_are_limited(db_session):
    workspace = await _workspace(db_session, "kw-limit")
    for index in range(6):
        await _add(db_session, workspace, f"f{index}.py", f"f{index}.py", "shared keyword here")

    results = await ArtifactRepository(db_session).search_fulltext(workspace.id, "keyword", limit=4)

    assert len(results) == 4


@pytest.mark.asyncio
@pytest.mark.parametrize("question", ['"-&():|', "?!...", "", "   ", "a b c"])
async def test_punctuation_and_syntax_only_questions_return_nothing_without_error(
    db_session, question
):
    workspace = await _workspace(db_session, "kw-syntax")
    await _add(db_session, workspace, "x.py", "x.py", "some content")

    assert await ArtifactRepository(db_session).search_fulltext(workspace.id, question) == []


@pytest.mark.asyncio
async def test_search_syntax_characters_inside_a_real_question_do_not_break_the_query(db_session):
    workspace = await _workspace(db_session, "kw-syntax-mixed")
    target = await _add(db_session, workspace, "x.py", "x.py", "login retry logic")

    results = await ArtifactRepository(db_session).search_fulltext(
        workspace.id, 'login & (retry) | "logic" -x :y'
    )

    assert [a.id for a in results] == [target.id]


@pytest.mark.asyncio
async def test_stop_words_only_question_returns_nothing_without_error(db_session):
    workspace = await _workspace(db_session, "kw-stopwords")
    await _add(db_session, workspace, "x.py", "x.py", "the and of to be")

    assert await ArtifactRepository(db_session).search_fulltext(workspace.id, "the and of") == []


@pytest.mark.asyncio
async def test_identifier_with_underscores_is_findable_by_its_words(db_session):
    workspace = await _workspace(db_session, "kw-identifiers")
    target = await _add(db_session, workspace, "spin.py", "spin.py", "def spin_widget(): pass")

    results = await ArtifactRepository(db_session).search_fulltext(workspace.id, "spin widget")

    assert [a.id for a in results] == [target.id]


@pytest.mark.asyncio
async def test_another_workspaces_matching_artifact_is_never_returned(db_session):
    mine = await _workspace(db_session, "kw-isolation-a")
    theirs = await _workspace(db_session, "kw-isolation-b")
    await _add(db_session, theirs, "secret.py", "secret.py", "confidential login retry details")

    assert await ArtifactRepository(db_session).search_fulltext(mine.id, "login retry") == []
