"""Tests for the MOCK feature scaffolding: slot holds + payment gate."""
import datetime

import pytest
from jose import jwt

from fast_api_services.tests.conftest import TEST_SECRET_KEY as TEST_SECRET


def _make_jwt(user_id: int = 1) -> str:
    return jwt.encode(
        {"user_id": user_id, "username": "tester"}, TEST_SECRET, algorithm="HS256"
    )


class TestSlotHold:
    @pytest.mark.asyncio
    async def test_hold_acquire_and_release(self, fake_redis):
        from fast_api_services.services.slot_cache import (
            get_hold,
            hold_slot,
            release_slot,
        )

        assert await hold_slot(fake_redis, slot_id=7, user_id=1, ttl_seconds=60) is True
        assert await get_hold(fake_redis, 7) == "1"

        # Another user cannot take it while held.
        assert await hold_slot(fake_redis, slot_id=7, user_id=2, ttl_seconds=60) is False
        # The owner still holds it.
        assert await hold_slot(fake_redis, slot_id=7, user_id=1, ttl_seconds=60) is True
        # Non-owner cannot release.
        assert await release_slot(fake_redis, slot_id=7, user_id=2) is False
        assert await release_slot(fake_redis, slot_id=7, user_id=1) is True
        assert await get_hold(fake_redis, 7) is None


class TestPaymentGate:
    @pytest.mark.asyncio
    async def test_pay_requires_confirm_true(self):
        from unittest.mock import AsyncMock

        from httpx import ASGITransport, AsyncClient

        from fast_api_services.database import get_db
        from fast_api_services.main import app

        mock_db = AsyncMock()
        app.dependency_overrides[get_db] = lambda: (x for x in [mock_db])

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            resp = await ac.post(
                "/api/bookings/10/pay",
                json={"method": "MOCK", "confirm": False},
                headers={"Authorization": f"Bearer {_make_jwt()}"},
            )

        app.dependency_overrides.clear()
        assert resp.status_code == 422
        assert "confirm" in resp.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_refund_requires_confirm_true(self):
        from unittest.mock import AsyncMock

        from httpx import ASGITransport, AsyncClient

        from fast_api_services.database import get_db
        from fast_api_services.main import app

        mock_db = AsyncMock()
        app.dependency_overrides[get_db] = lambda: (x for x in [mock_db])

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            resp = await ac.post(
                "/api/bookings/10/refund",
                json={"confirm": False},
                headers={"Authorization": f"Bearer {_make_jwt()}"},
            )

        app.dependency_overrides.clear()
        assert resp.status_code == 422
