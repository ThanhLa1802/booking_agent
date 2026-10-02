"""Integration-level tests for catalog endpoints (mock DB)."""
import datetime
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


def _make_jwt(user_id: int = 1) -> str:
    from jose import jwt

    from fast_api_services.tests.conftest import TEST_SECRET_KEY
    return jwt.encode(
        {"user_id": user_id, "username": "tester"},
        TEST_SECRET_KEY,
        algorithm="HS256",
    )


class TestCatalogEndpoints:
    @pytest.mark.asyncio
    async def test_get_instruments_returns_list(self):
        from httpx import ASGITransport, AsyncClient

        from fast_api_services.database import get_db
        from fast_api_services.main import app
        from fast_api_services.schemas.models import InstrumentOut

        mock_instruments = [
            InstrumentOut(id=1, name="Piano", style="CLASSICAL_JAZZ", style_display="Classical & Jazz"),
        ]

        with patch(
            "fast_api_services.routers.catalog.list_instruments",
            new=AsyncMock(return_value=mock_instruments),
        ):
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as ac:
                resp = await ac.get("/api/catalog/instruments")

        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["name"] == "Piano"

    @pytest.mark.asyncio
    async def test_get_courses_returns_list(self):
        from httpx import ASGITransport, AsyncClient

        from fast_api_services.main import app
        from fast_api_services.schemas.models import CourseOut

        mock_courses = [
            CourseOut(
                id=1,
                instrument_id=1,
                instrument_name="Piano",
                style="CLASSICAL_JAZZ",
                style_display="Classical & Jazz",
                grade=1,
                name="Piano Grade 1",
                description="Beginner piano",
                duration_minutes=10,
                fee=Decimal("800000"),
            )
        ]

        with patch(
            "fast_api_services.routers.catalog.list_courses",
            new=AsyncMock(return_value=mock_courses),
        ):
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as ac:
                resp = await ac.get("/api/catalog/courses?grade=1")

        assert resp.status_code == 200
        data = resp.json()
        assert data[0]["grade"] == 1

    @pytest.mark.asyncio
    async def test_get_slots_returns_available(self):
        from httpx import ASGITransport, AsyncClient

        from fast_api_services.main import app
        from fast_api_services.schemas.models import ExamSlotOut

        mock_slots = [
            ExamSlotOut(
                id=1,
                center_id=1,
                center_name="Trinity Hanoi",
                center_city="Hanoi",
                course_id=1,
                course_name="Piano Grade 1",
                instrument_name="Piano",
                grade=1,
                style="CLASSICAL_JAZZ",
                style_display="Classical & Jazz",
                fee=Decimal("500000"),
                exam_date=datetime.date(2025, 3, 15),
                start_time=datetime.time(9, 0),
                capacity=5,
                available_capacity=5,
            )
        ]

        with patch(
            "fast_api_services.routers.catalog.list_available_slots",
            new=AsyncMock(return_value=mock_slots),
        ):
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as ac:
                resp = await ac.get("/api/catalog/slots")

        assert resp.status_code == 200
        assert resp.json()[0]["center_city"] == "Hanoi"

    @pytest.mark.asyncio
    async def test_get_course_404_when_not_found(self):
        from httpx import ASGITransport, AsyncClient

        from fast_api_services.main import app

        with patch(
            "fast_api_services.routers.catalog.get_course",
            new=AsyncMock(return_value=None),
        ):
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as ac:
                resp = await ac.get("/api/catalog/courses/9999")

        assert resp.status_code == 404
