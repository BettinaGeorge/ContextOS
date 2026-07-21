import pytest

from src.models.connector import SourceSystem
from src.models.workspace import Workspace
from src.repositories.connector_repository import ConnectorRepository, decrypt_token


@pytest.mark.asyncio
async def test_connector_repository_never_persists_plaintext_token(db_session):
    workspace = Workspace(owner_user_id="test-user", name="Test")
    db_session.add(workspace)
    await db_session.commit()
    await db_session.refresh(workspace)

    raw_token = "ghp_supersecretplaintexttoken"
    repo = ConnectorRepository(db_session)
    connector = await repo.create(
        workspace_id=workspace.id,
        source_system=SourceSystem.github,
        raw_access_token=raw_token,
        external_resource_ref="acme/widgets",
    )

    assert connector.encrypted_access_token != raw_token
    assert raw_token not in connector.encrypted_access_token

    stored = await repo.get_by_id(workspace.id, connector.id)
    assert stored is not None
    assert stored.encrypted_access_token != raw_token
    assert decrypt_token(stored.encrypted_access_token) == raw_token
    assert await repo.decrypt_for_use(stored) == raw_token
