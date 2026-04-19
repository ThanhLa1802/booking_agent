"""Integration-level tests for catalog endpoints (mock DB)."""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from decimal import Decimal
import datetime


def _make_jwt(user_id: int = 1) -> str:
    from jose import jwt
    return jwt.encode(
        {"user_id": user_id, "username": "tester"},
        "dev-secret-key-change-in-production-1234567890abcdef",
        algorithm="HS256",
    )


class TestCatalogEndpoints:
    @pytest.mark.asyncio
    async def test_get_instruments_returns_list(self):
        from fast_api_services.main import app
        from fast_api_services.database import get_db
        from fast_api_services.schemas.models import InstrumentOut
        from httpx import AsyncClient, ASGITransport

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
        from fast_api_services.main import app
        from fast_api_services.schemas.models import CourseOut
        from httpx import AsyncClient, ASGITransport

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
        from fast_api_services.main import app
        from fast_api_services.schemas.models import ExamSlotOut
        from httpx import AsyncClient, ASGITransport

        mock_slots = [
            ExamSlotOut(
                id=1,
                center_id=1,
                center_name="Trinity Hanoi",
                center_city="Hanoi",
                course_id=1,
                course_name="Piano Grade 1",
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
        from fast_api_services.main import app
        from httpx import AsyncClient, ASGITransport

        with patch(
            "fast_api_services.routers.catalog.get_course",
            new=AsyncMock(return_value=None),
        ):
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as ac:
                resp = await ac.get("/api/catalog/courses/9999")

        assert resp.status_code == 404
