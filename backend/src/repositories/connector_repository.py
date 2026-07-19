import uuid
from datetime import datetime

from cryptography.fernet import Fernet
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config import get_settings
from src.models.connector import Connector, ConnectorStatus, SourceSystem


def _cipher() -> Fernet:
    return Fernet(get_settings().token_encryption_key)


def encrypt_token(raw_token: str) -> str:
    return _cipher().encrypt(raw_token.encode()).decode()


def decrypt_token(encrypted_token: str) -> str:
    return _cipher().decrypt(encrypted_token.encode()).decode()


class ConnectorRepository:
    """FR-016 / Constitution Principle III: encrypts the access token before
    every write and decrypts only at the point of use. No method on this
    class accepts or returns a raw token except decrypt_for_use — a
    connector row is never persisted with a plaintext token, even
    transiently. (Fixed here in Foundational per the /speckit-analyze C1
    finding — this was originally deferred to Polish, which would have let
    the MVP checkpoint ship with plaintext tokens.)
    """

    def __init__(self, session: AsyncSession):
        self._session = session

    async def create(
        self,
        workspace_id: uuid.UUID,
        source_system: SourceSystem,
        raw_access_token: str,
        external_resource_ref: str,
    ) -> Connector:
        connector = Connector(
            workspace_id=workspace_id,
            source_system=source_system,
            status=ConnectorStatus.connected,
            encrypted_access_token=encrypt_token(raw_access_token),
            external_resource_ref=external_resource_ref,
        )
        self._session.add(connector)
        await self._session.commit()
        await self._session.refresh(connector)
        return connector

    async def decrypt_for_use(self, connector: Connector) -> str:
        return decrypt_token(connector.encrypted_access_token)

    async def get_by_id(self, workspace_id: uuid.UUID, connector_id: uuid.UUID) -> Connector | None:
        result = await self._session.execute(
            select(Connector).where(
                Connector.workspace_id == workspace_id, Connector.id == connector_id
            )
        )
        return result.scalar_one_or_none()

    async def get_by_workspace_and_source(
        self, workspace_id: uuid.UUID, source_system: SourceSystem
    ) -> Connector | None:
        result = await self._session.execute(
            select(Connector).where(
                Connector.workspace_id == workspace_id, Connector.source_system == source_system
            )
        )
        return result.scalar_one_or_none()

    async def update_status(
        self,
        connector: Connector,
        status: ConnectorStatus,
        error_message: str | None = None,
        last_ingested_at: datetime | None = None,
    ) -> Connector:
        connector.status = status
        connector.error_message = error_message
        if last_ingested_at is not None:
            connector.last_ingested_at = last_ingested_at
        await self._session.commit()
        await self._session.refresh(connector)
        return connector
