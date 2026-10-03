"""
Tests for the EXAMINER self-service flow: read-only own-schedule tools,
role routing, and the /api/scheduling/me/schedule/ endpoint (JWT-scoped).
"""
from __future__ import annotations

from datetime import date, time
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from fast_api_services.agent.examiner_tools import (
    _LINKED_REQUIRED,
    ExaminerToolContext,
    make_examiner_tools,
)
from fast_api_services.schemas.models import (
    ExaminerOut,
    ExaminerScheduleOut,
    ExamSlotScheduleOut,
)

# ── helpers ───────────────────────────────────────────────────────────────────

def _session_factory():
    sm = MagicMock()
    sm.return_value = MagicMock()
    sm.return_value.__aenter__ = AsyncMock(return_value=AsyncMock())
    sm.return_value.__aexit__ = AsyncMock(return_value=False)
    return sm


def _ctx(examiner_id):
    return ExaminerToolContext(
        session_factory=_session_factory(),
        examiner_id=examiner_id,
        user_id=7,
    )


def _fake_schedule():
    examiner = ExaminerOut(
        id=1,
        center_id=3,
        center_name="Center A",
        center_city="Hanoi",
        name="Giao Vien A",
        email="gv.a@example.com",
        phone="",
        specialization_names=["Piano"],
        max_exams_per_day=8,
        is_active=True,
    )
    slot = ExamSlotScheduleOut(
        id=10,
        center_id=3,
        center_name="Center A",
        center_city="Hanoi",
        course_id=2,
        course_name="Piano Grade 1",
        instrument_name="Piano",
        grade=1,
        style="CLASSICAL_JAZZ",
        style_display="Classical & Jazz",
        fee=Decimal("100"),
        exam_date=date(2026, 6, 1),
        start_time=time(9, 0),
        capacity=4,
        available_capacity=1,
    )
    return ExaminerScheduleOut(examiner=examiner, slots=[slot])


class _FakeResult:
    def __init__(self, row):
        self._row = row

    def mappings(self):
        return self

    def first(self):
        return self._row


class _FakeDB:
    def __init__(self, row):
        self._row = row

    async def execute(self, *_args, **_kwargs):
        return _FakeResult(self._row)


# ── tool: scoped read-only ─────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_get_my_schedule_without_linked_examiner():
    tools = make_examiner_tools(_ctx(examiner_id=None))
    tool = next(t for t in tools if t.name == "get_my_schedule")

    result = await tool.ainvoke({})

    assert result == _LINKED_REQUIRED


@pytest.mark.asyncio
async def test_get_my_schedule_uses_server_side_examiner_id_only():
    tools = make_examiner_tools(_ctx(examiner_id=55))
    tool = next(t for t in tools if t.name == "get_my_schedule")

    with patch(
        "fast_api_services.services.examiner_service.get_examiner_schedule",
        new=AsyncMock(return_value=_fake_schedule()),
    ) as mock_schedule:
        result = await tool.ainvoke({"date_from": "2026-06-01", "date_to": "2026-06-30"})

    # The examiner id comes from the context, never from the model's arguments.
    assert mock_schedule.await_args.args[1] == 55
    assert "Giao Vien A" in result
    assert "Piano Grade 1" in result
    assert "2026-06-01" in result
    assert "09:00" in result
    assert "3/4" in result


@pytest.mark.asyncio
async def test_get_my_schedule_never_accepts_examiner_id_argument():
    tools = make_examiner_tools(_ctx(examiner_id=55))
    tool = next(t for t in tools if t.name == "get_my_schedule")

    # The tool schema exposes no examiner_id — the context id is authoritative.
    assert set(tool.args.keys()) == {"date_from", "date_to"}


# ── service: lookup by user ────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_get_examiner_by_user_id_none_when_unlinked():
    from fast_api_services.services.examiner_service import get_examiner_by_user_id

    assert await get_examiner_by_user_id(_FakeDB(None), user_id=7) is None


@pytest.mark.asyncio
async def test_get_examiner_by_user_id_returns_examiner():
    from fast_api_services.services.examiner_service import get_examiner_by_user_id

    row = {
        "id": 1,
        "center_id": 3,
        "center_name": "Center A",
        "center_city": "Hanoi",
        "name": "Giao Vien A",
        "email": "gv.a@example.com",
        "phone": "",
        "max_exams_per_day": 8,
        "is_active": True,
        "specialization_names": "Piano (CLASSICAL_JAZZ)",
    }
    examiner = await get_examiner_by_user_id(_FakeDB(row), user_id=7)

    assert examiner is not None
    assert examiner.id == 1
    assert examiner.name == "Giao Vien A"


# ── routing ───────────────────────────────────────────────────────────────────

def test_route_examiner_to_examiner_subgraph():
    from fast_api_services.agent.supervisor import _route_by_role

    assert _route_by_role({"user_role": "EXAMINER"}) == "examiner_subgraph"


# ── endpoint: role guard + JWT scoping ────────────────────────────────────────

@pytest.fixture
def authed_client(client):
    ac, mock_db, fake_redis = client
    from fast_api_services.auth import TokenPayload, get_current_user
    from fast_api_services.main import app

    async def override_user():
        return TokenPayload(user_id=7, username="gv@example.com", raw_token="tok")

    app.dependency_overrides[get_current_user] = override_user
    return ac, mock_db, fake_redis


@pytest.mark.asyncio
async def test_my_schedule_forbidden_for_non_examiner(authed_client):
    ac, _, _ = authed_client
    with patch(
        "fast_api_services.routers.scheduling._load_role",
        new=AsyncMock(return_value="STUDENT"),
    ):
        resp = await ac.get("/api/scheduling/me/schedule/")
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_my_schedule_returns_own_schedule(authed_client):
    ac, _, _ = authed_client
    examiner = _fake_schedule().examiner
    with (
        patch(
            "fast_api_services.routers.scheduling._load_role",
            new=AsyncMock(return_value="EXAMINER"),
        ),
        patch(
            "fast_api_services.routers.scheduling.get_examiner_by_user_id",
            new=AsyncMock(return_value=examiner),
        ),
        patch(
            "fast_api_services.routers.scheduling.get_examiner_schedule",
            new=AsyncMock(return_value=_fake_schedule()),
        ) as mock_schedule,
    ):
        resp = await ac.get("/api/scheduling/me/schedule/")

    assert resp.status_code == 200
    assert resp.json()["examiner"]["name"] == "Giao Vien A"
    # Server resolves the examiner from the JWT, not from a query param.
    assert mock_schedule.await_args.args[1] == examiner.id


@pytest.mark.asyncio
async def test_my_schedule_404_when_account_unlinked(authed_client):
    ac, _, _ = authed_client
    with (
        patch(
            "fast_api_services.routers.scheduling._load_role",
            new=AsyncMock(return_value="EXAMINER"),
        ),
        patch(
            "fast_api_services.routers.scheduling.get_examiner_by_user_id",
            new=AsyncMock(return_value=None),
        ),
    ):
        resp = await ac.get("/api/scheduling/me/schedule/")
    assert resp.status_code == 404


# ── endpoint: create examiner (proxied to Django) ─────────────────────────────

@pytest.mark.asyncio
async def test_create_examiner_forbidden_for_non_admin(authed_client):
    ac, _, _ = authed_client
    with patch(
        "fast_api_services.routers.scheduling._load_role",
        new=AsyncMock(return_value="EXAMINER"),
    ):
        resp = await ac.post(
            "/api/scheduling/examiners/",
            json={"name": "X", "email": "x@example.com"},
        )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_create_examiner_proxies_to_django_with_password(authed_client):
    ac, _, _ = authed_client
    mock_response = MagicMock()
    mock_response.status_code = 201
    mock_response.json.return_value = {"id": 5, "name": "GV E", "has_login": True}

    with (
        patch(
            "fast_api_services.routers.scheduling._load_role",
            new=AsyncMock(return_value="CENTER_ADMIN"),
        ),
        patch("httpx.AsyncClient") as mock_client_cls,
    ):
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)

        resp = await ac.post(
            "/api/scheduling/examiners/",
            json={
                "name": "GV E",
                "email": "gv.e@example.com",
                "password": "strongpass123",
                "specializations": [1, 2],
            },
        )

    assert resp.status_code == 201
    assert resp.json()["has_login"] is True

    args, kwargs = mock_client.post.await_args
    assert args[0].endswith("/api/centers/examiners/")
    assert kwargs["json"]["password"] == "strongpass123"
    assert kwargs["json"]["specializations"] == [1, 2]


@pytest.mark.asyncio
async def test_create_examiner_without_password_omits_it(authed_client):
    ac, _, _ = authed_client
    mock_response = MagicMock()
    mock_response.status_code = 201
    mock_response.json.return_value = {"id": 6, "name": "GV F", "has_login": False}

    with (
        patch(
            "fast_api_services.routers.scheduling._load_role",
            new=AsyncMock(return_value="CENTER_ADMIN"),
        ),
        patch("httpx.AsyncClient") as mock_client_cls,
    ):
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)

        resp = await ac.post(
            "/api/scheduling/examiners/",
            json={"name": "GV F", "email": "gv.f@example.com", "password": ""},
        )

    assert resp.status_code == 201
    _, kwargs = mock_client.post.await_args
    assert "password" not in kwargs["json"]
