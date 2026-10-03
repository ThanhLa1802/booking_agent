"""Tests for booking endpoints — confirmation gate and slot hold logic."""
import datetime
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from jose import jwt

from fast_api_services.tests.conftest import TEST_SECRET_KEY as TEST_SECRET


def _make_jwt(user_id: int = 1) -> str:
    return jwt.encode(
        {"user_id": user_id, "username": "tester"},
        TEST_SECRET,
        algorithm="HS256",
    )


def _make_booking_out():
    from fast_api_services.schemas.models import BookingOut, SlotDetail
    return BookingOut(
        id=10,
        slot_id=1,
        slot_detail=SlotDetail(
            center="Trinity Hanoi",
            city="Hanoi",
            course="Piano Grade 1",
            exam_date=datetime.date(2025, 3, 15),
            start_time=datetime.time(9, 0),
        ),
        student_name="Nguyen Van A",
        student_dob=datetime.date(2010, 5, 1),
        status="CONFIRMED",
        notes="",
        created_at=datetime.datetime(2025, 1, 1, 12, 0),
    )


class TestBookingConfirmationGate:
    @pytest.mark.asyncio
    async def test_create_booking_requires_confirm_true(self):
        from httpx import ASGITransport, AsyncClient

        from fast_api_services.database import get_db
        from fast_api_services.main import app

        mock_db = AsyncMock()
        app.dependency_overrides[get_db] = lambda: (x for x in [mock_db])

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            resp = await ac.post(
                "/api/bookings",
                json={
                    "slot_id": 1,
                    "student_name": "Test Student",
                    "student_dob": "2010-01-01",
                    "confirm": False,
                },
                headers={"Authorization": f"Bearer {_make_jwt()}"},
            )

        app.dependency_overrides.clear()
        assert resp.status_code == 422
        assert "confirm" in resp.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_cancel_booking_requires_confirm_true(self):
        from httpx import ASGITransport, AsyncClient

        from fast_api_services.database import get_db
        from fast_api_services.main import app

        mock_db = AsyncMock()
        booking = _make_booking_out()

        app.dependency_overrides[get_db] = lambda: (x for x in [mock_db])

        with patch(
            "fast_api_services.routers.bookings.get_booking",
            new=AsyncMock(return_value=booking),
        ):
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as ac:
                resp = await ac.post(
                    "/api/bookings/10/cancel",
                    json={"reason": "", "confirm": False},
                    headers={"Authorization": f"Bearer {_make_jwt()}"},
                )

        app.dependency_overrides.clear()
        assert resp.status_code == 422
        assert "confirm" in resp.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_bookings_list_requires_auth(self):
        from httpx import ASGITransport, AsyncClient

        from fast_api_services.main import app

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            resp = await ac.get("/api/bookings")

        assert resp.status_code in (401, 403)  # HTTPBearer: 403 when creds missing
