"""Runs the baseline questions through keyword search and reports which ones find the
artifact they should (specs/003-reliability-hardening, T002/T003/T034).

Run it from backend/ against the database you have ingested into:

    uv run python -m scripts.keyword_baseline --list-workspaces
    uv run python -m scripts.keyword_baseline --workspace-id <uuid>

It calls `ArtifactRepository.search_fulltext` exactly as retrieval does and looks only at
the first ten results, so the same command gives comparable numbers before and after the
search change."""

import argparse
import asyncio
import re
import subprocess
import uuid
from dataclasses import dataclass
from pathlib import Path

BASELINE_FILE = Path(__file__).resolve().parents[2] / "specs/003-reliability-hardening/baseline.md"
RESULT_WINDOW = 10

URL_BASE_RE = re.compile(r"^URL base:\s*`([^`]+)`", re.MULTILINE)
ROW_RE = re.compile(r"^\|\s*(Q\d+)\s*\|\s*(.+?)\s*\|\s*`([^`]+)`\s*\|\s*$", re.MULTILINE)


@dataclass(frozen=True)
class BaselineQuestion:
    label: str
    question: str
    expected_url: str


def parse_questions(markdown: str) -> list[BaselineQuestion]:
    base_match = URL_BASE_RE.search(markdown)
    if base_match is None:
        raise ValueError("baseline file has no 'URL base: `...`' line")
    base = base_match.group(1)
    return [
        BaselineQuestion(label, question, base + path)
        for label, question, path in ROW_RE.findall(markdown)
    ]


def rank_of_expected(expected_url: str, result_urls: list[str]) -> int | None:
    """1-based position of the first result whose URL is the expected file, ignoring the
    `#L1-L20` line anchor that chunk pieces carry. None when it is not in the window."""
    for position, url in enumerate(result_urls[:RESULT_WINDOW], start=1):
        if url.split("#")[0] == expected_url:
            return position
    return None


def _git_commit() -> str:
    try:
        return subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True, check=True
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


async def _list_workspaces() -> None:
    from sqlalchemy import func, select

    from src.core.db import async_session_factory
    from src.models.artifact import Artifact
    from src.models.workspace import Workspace

    async with async_session_factory() as session:
        rows = await session.execute(
            select(Workspace.id, Workspace.name, func.count(Artifact.id))
            .outerjoin(Artifact, Artifact.workspace_id == Workspace.id)
            .group_by(Workspace.id, Workspace.name)
        )
        for workspace_id, name, artifact_count in rows.all():
            print(f"{workspace_id}  {name}  ({artifact_count} artifacts)")


async def _run(workspace_id: uuid.UUID, questions: list[BaselineQuestion]) -> None:
    from src.core.db import async_session_factory
    from src.repositories.artifact_repository import ArtifactRepository

    found = 0
    async with async_session_factory() as session:
        repo = ArtifactRepository(session)
        for item in questions:
            results = await repo.search_fulltext(workspace_id, item.question)
            rank = rank_of_expected(item.expected_url, [a.source_url for a in results])
            found += rank is not None
            outcome = f"FOUND at rank {rank}" if rank else "MISSED"
            print(f"{item.label:<4} {outcome:<18} {item.question}")
    print(
        f"\n{found} of {len(questions)} questions found their expected artifact "
        f"in the top {RESULT_WINDOW}."
    )
    print(f"commit: {_git_commit()}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--workspace-id", type=uuid.UUID)
    parser.add_argument("--list-workspaces", action="store_true")
    args = parser.parse_args()

    if args.list_workspaces:
        asyncio.run(_list_workspaces())
        return
    if args.workspace_id is None:
        parser.error("pass --workspace-id (find it with --list-workspaces)")
    questions = parse_questions(BASELINE_FILE.read_text())
    if not questions:
        parser.error(f"no questions found in {BASELINE_FILE}")
    asyncio.run(_run(args.workspace_id, questions))


if __name__ == "__main__":
    main()
