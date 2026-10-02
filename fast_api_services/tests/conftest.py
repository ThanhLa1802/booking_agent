import os

# Set a non-default SECRET_KEY before any app modules are imported.
# This satisfies the startup validator in config.py and is used by tests
# that create JWTs (see TEST_SECRET in test_bookings.py / test_catalog.py).
TEST_SECRET_KEY = "test-secret-key-for-tests-not-for-production-abc123"
os.environ.setdefault("SECRET_KEY", TEST_SECRET_KEY)

from unittest.mock import AsyncMock, patch

import fakeredis.aioredis as fake_aioredis
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient


@pytest.fixture(scope="session")
def anyio_backend():
    return "asyncio"


@pytest.fixture(autouse=True)
def _reset_sse_app_status():
    """
    sse-starlette caches a module-level anyio.Event (AppStatus.should_exit_event)
    that gets bound to the first event loop it is created in. With function-scoped
    loops, later SSE tests fail with 'bound to a different event loop'. Reset the
    cached state around every test so each loop creates its own Event.
    """
    import sse_starlette.sse as _sse

    _sse.AppStatus.should_exit_event = None
    _sse.AppStatus.should_exit = False
    yield
    _sse.AppStatus.should_exit_event = None
    _sse.AppStatus.should_exit = False


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
    from fast_api_services import services
    from fast_api_services.database import get_db
    from fast_api_services.main import app

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
