"""Ingests every connector of one workspace straight into the database in DATABASE_URL, then
extracts relationships. Used to rebuild data on a migrated copy (specs/003, T013) and to
show that a second run changes nothing and embeds nothing.

    export DATABASE_URL=postgresql+asyncpg://localhost:5433/contextos_dev_copy
    uv run python -m scripts.ingest_workspace --workspace-id <uuid> --confirm contextos_dev_copy

It calls the real GitHub and Notion APIs and the real embedding service, so it spends
embedding quota. `--confirm` must name the database it will write to."""

import argparse
import asyncio
import uuid
from urllib.parse import urlparse


def database_name(url: str) -> str:
    return urlparse(url).path.lstrip("/")


async def _run(workspace_id: uuid.UUID) -> None:
    from sqlalchemy import func, select

    from src.core.db import async_session_factory
    from src.llm.voyage_client import VoyageClient
    from src.models.artifact import Artifact
    from src.models.relationship import Relationship
    from src.repositories.connector_repository import ConnectorRepository
    from src.services.connector_svc import ConnectorService
    from src.services.relationship_svc import RelationshipService

    class CountingVoyage(VoyageClient):
        def __init__(self):
            super().__init__()
            self.texts_embedded = 0

        def embed_documents(self, texts):
            self.texts_embedded += len(texts)
            return super().embed_documents(texts)

    async def count(session, model) -> int:
        result = await session.execute(
            select(func.count()).select_from(model).where(model.workspace_id == workspace_id)
        )
        return result.scalar_one()

    voyage = CountingVoyage()
    async with async_session_factory() as session:
        connectors = await ConnectorRepository(session).list_by_workspace(workspace_id)
        if not connectors:
            raise SystemExit("this workspace has no connectors")
        print(f"before: {await count(session, Artifact)} artifacts, "
              f"{await count(session, Relationship)} relationships")
        for connector in connectors:
            rows = await ConnectorService(session, voyage_client=voyage).ingest(
                workspace_id, connector
            )
            print(f"ingested {connector.source_system}: {rows} pieces")
        created = await RelationshipService(session).extract_for_workspace(workspace_id)
        print(f"new relationships: {created}")
        print(f"after:  {await count(session, Artifact)} artifacts, "
              f"{await count(session, Relationship)} relationships")
        print(f"texts sent to the embedding service this run: {voyage.texts_embedded}")


def main() -> None:
    from src.core.config import get_settings

    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--workspace-id", type=uuid.UUID, required=True)
    parser.add_argument("--confirm", required=True, help="name of the database to write to")
    args = parser.parse_args()

    target = database_name(get_settings().database_url)
    if args.confirm != target:
        parser.error(f"--confirm must equal the target database name: {target!r}")
    print(f"writing to database: {target}")
    asyncio.run(_run(args.workspace_id))


if __name__ == "__main__":
    main()
