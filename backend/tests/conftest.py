import time
import uuid

import jwt
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config import get_settings
from src.core.db import async_session_factory
from src.main import app


@pytest.fixture
async def db_session() -> AsyncSession:
    async with async_session_factory() as session:
        yield session


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.fixture
def make_jwt():
    """Signs a JWT the same way a real Supabase Auth token would be
    verified — HS256 with the project's JWT secret — so contract/integration
    tests exercise the real verification path without needing a live
    Supabase project."""

    def _make(user_id: str | None = None) -> str:
        settings = get_settings()
        uid = user_id or f"test-user-{uuid.uuid4()}"
        return jwt.encode(
            {"sub": uid, "aud": "authenticated", "exp": int(time.time()) + 3600},
            settings.supabase_jwt_secret,
            algorithm="HS256",
        )

    return _make
