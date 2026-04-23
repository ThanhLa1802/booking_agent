import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from unittest.mock import AsyncMock, patch
import fakeredis.aioredis as fake_aioredis


@pytest.fixture(scope="session")
def anyio_backend():
    return "asyncio"


@pytest_asyncio.fixture
async def fake_redis():
    """In-memory Redis substitute."""
    r = fake_aioredis.FakeRedis(decode_responses=True)
    yield r
    await r.aclose()


@pytest_asyncio.fixture
async def client(fake_redis):
    """
    HTTPX AsyncClient wired to the FastAPI app.
    DB calls and Redis are mocked.
    """
    from fast_api_services.main import app
    from fast_api_services.database import get_db
    from fast_api_services import services

    # Patch Redis client
    with patch("fast_api_services.services.slot_cache._redis_client", fake_redis):
        # Patch DB dependency with a no-op session
        mock_db = AsyncMock()

        async def override_db():
            yield mock_db

        app.dependency_overrides[get_db] = override_db

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            yield ac, mock_db, fake_redis

        app.dependency_overrides.clear()
