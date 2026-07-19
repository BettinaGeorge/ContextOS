import uuid
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from src.connectors.base import ConnectorAuthError
from src.core.job_worker import register_handler
from src.models.connector import ConnectorStatus
from src.models.job import Job, JobType
from src.repositories.connector_repository import ConnectorRepository
from src.repositories.job_repository import JobRepository
from src.services.connector_svc import ConnectorService
from src.services.relationship_svc import RelationshipService

_JOB_TYPE_FOR_SOURCE = {
    "github": JobType.ingest_github,
    "notion": JobType.ingest_notion,
}


class IngestionService:
    def __init__(self, session: AsyncSession):
        self._session = session
        self._jobs = JobRepository(session)
        self._connectors = ConnectorRepository(session)

    async def trigger(self, workspace_id: uuid.UUID, connector_id: uuid.UUID) -> Job:
        connector = await self._connectors.get_by_id(workspace_id, connector_id)
        if connector is None:
            raise ValueError(f"No connector {connector_id} in workspace {workspace_id}")
        await self._connectors.update_status(connector, ConnectorStatus.ingesting)
        job_type = _JOB_TYPE_FOR_SOURCE[connector.source_system]
        return await self._jobs.enqueue(workspace_id, connector_id, job_type)


async def _handle_ingestion_job(job: Job, session: AsyncSession) -> None:
    """Registered with job_worker (T022) — this is what the in-process poller
    actually runs for ingest_github/ingest_notion jobs."""
    connector_repo = ConnectorRepository(session)
    connector = await connector_repo.get_by_id(job.workspace_id, job.connector_id)
    if connector is None:
        raise ValueError(f"Connector {job.connector_id} not found for job {job.id}")

    try:
        await ConnectorService(session).ingest(job.workspace_id, connector)
        await RelationshipService(session).extract_for_workspace(job.workspace_id)
        await connector_repo.update_status(
            connector, ConnectorStatus.complete, last_ingested_at=datetime.now(UTC)
        )
    except ConnectorAuthError as exc:
        # T055: distinguish "the credential itself is bad" from other
        # failures — the user's next step is genuinely different (reconnect
        # with a new token, not just retry the same one).
        await connector_repo.update_status(
            connector, ConnectorStatus.needs_reconnect, error_message=str(exc)
        )
        raise
    except Exception as exc:
        # Surface the failure on the connector too, not just the job row, so
        # GET /connectors/{id}/status reflects it.
        await connector_repo.update_status(
            connector, ConnectorStatus.failed, error_message=str(exc)
        )
        raise


register_handler(JobType.ingest_github, _handle_ingestion_job)
register_handler(JobType.ingest_notion, _handle_ingestion_job)
