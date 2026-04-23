"""
Tests for CENTER_ADMIN scheduling tools.

Covers:
1. Confirmation gate — assign_examiner_to_slot / reschedule_booking without confirm
2. assign_examiner_to_slot with confirm=True — success path
3. assign_examiner_to_slot with confirm=True — Django error forwarded
4. reschedule_booking with confirm=True — success path
5. list_examiners — returns formatted string
6. suggest_examiners_for_slot — returns ranked list
7. get_exam_calendar — returns calendar string
8. make_reschedule_tools — suggest_slots_for_reschedule confirm gate
"""
from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from fast_api_services.agent.scheduling_tools import (
    SchedulingToolContext,
    _CONFIRM_REQUIRED,
    make_reschedule_tools,
    make_scheduling_tools,
)


@pytest.fixture
def sched_ctx():
    sm = MagicMock()
    sm.return_value = MagicMock()
    sm.return_value.__aenter__ = AsyncMock(return_value=AsyncMock())
    sm.return_value.__aexit__ = AsyncMock(return_value=False)
    return SchedulingToolContext(
        session_factory=sm,
        user_token="test.jwt.token",
        center_id=1,
    )


# ── 1. Confirmation gate ──────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_assign_examiner_requires_confirm(sched_ctx):
    tools = make_scheduling_tools(sched_ctx)
    assign_tool = next(t for t in tools if t.name == "assign_examiner_to_slot")

    result = await assign_tool.ainvoke(
        {"slot_id": 5, "examiner_id": 2, "confirm": False}
    )

    assert _CONFIRM_REQUIRED in result
    assert "5" in result
    assert "2" in result


@pytest.mark.asyncio
async def test_reschedule_booking_requires_confirm(sched_ctx):
    tools = make_reschedule_tools(sched_ctx, user_id=42)
    reschedule_tool = next(t for t in tools if t.name == "reschedule_booking")

    result = await reschedule_tool.ainvoke(
        {"booking_id": 10, "new_slot_id": 20, "reason": "conflict", "confirm": False}
    )

    assert _CONFIRM_REQUIRED in result
    assert "10" in result
    assert "20" in result


# ── 2. assign_examiner_to_slot success ────────────────────────────────────────

@pytest.mark.asyncio
async def test_assign_examiner_success(sched_ctx):
    tools = make_scheduling_tools(sched_ctx)
    assign_tool = next(t for t in tools if t.name == "assign_examiner_to_slot")

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"examiner_name": "Nguyen Thi B"}

    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)

        result = await assign_tool.ainvoke(
            {"slot_id": 5, "examiner_id": 2, "confirm": True}
        )

    assert "✅" in result
    assert "Nguyen Thi B" in result


# ── 3. assign_examiner_to_slot — Django error forwarded ──────────────────────

@pytest.mark.asyncio
async def test_assign_examiner_django_error(sched_ctx):
    tools = make_scheduling_tools(sched_ctx)
    assign_tool = next(t for t in tools if t.name == "assign_examiner_to_slot")

    mock_response = MagicMock()
    mock_response.status_code = 409
    mock_response.text = "Examiner is unavailable on this date."

    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)

        result = await assign_tool.ainvoke(
            {"slot_id": 5, "examiner_id": 2, "confirm": True}
        )

    assert "❌" in result
    assert "409" in result


# ── 4. reschedule_booking success ─────────────────────────────────────────────

@pytest.mark.asyncio
async def test_reschedule_booking_success(sched_ctx):
    tools = make_reschedule_tools(sched_ctx, user_id=42)
    reschedule_tool = next(t for t in tools if t.name == "reschedule_booking")

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"slot": 20}

    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)

        result = await reschedule_tool.ainvoke(
            {"booking_id": 10, "new_slot_id": 20, "reason": "changed plans", "confirm": True}
        )

    assert "✅" in result
    assert "10" in result


# ── 5. list_examiners ─────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_list_examiners_returns_formatted_string(sched_ctx):
    tools = make_scheduling_tools(sched_ctx)
    list_tool = next(t for t in tools if t.name == "list_examiners")

    fake_examiner = MagicMock()
    fake_examiner.id = 1
    fake_examiner.name = "Tran Van C"
    fake_examiner.max_exams_per_day = 6
    fake_examiner.specialization_names = ["Piano", "Guitar"]

    with patch(
        "fast_api_services.services.examiner_service.list_examiners",
        AsyncMock(return_value=[fake_examiner]),
    ), patch(
        "fast_api_services.services.examiner_service.get_examiner_daily_load",
        AsyncMock(return_value=0),
    ):
        result = await list_tool.ainvoke({})

    assert "Tran Van C" in result
    assert "Piano" in result


@pytest.mark.asyncio
async def test_list_examiners_empty(sched_ctx):
    tools = make_scheduling_tools(sched_ctx)
    list_tool = next(t for t in tools if t.name == "list_examiners")

    with patch(
        "fast_api_services.services.examiner_service.list_examiners",
        AsyncMock(return_value=[]),
    ):
        result = await list_tool.ainvoke({})

    assert "No available" in result


# ── 6. suggest_examiners_for_slot ─────────────────────────────────────────────

@pytest.mark.asyncio
async def test_suggest_examiners_returns_ranked_list(sched_ctx):
    tools = make_scheduling_tools(sched_ctx)
    suggest_tool = next(t for t in tools if t.name == "suggest_examiners_for_slot")

    fake_suggestion = MagicMock()
    fake_suggestion.examiner = MagicMock(id=3, name="Le Thi D", max_exams_per_day=8)
    fake_suggestion.exams_today = 2

    with patch(
        "fast_api_services.services.examiner_service.suggest_examiners_for_slot",
        AsyncMock(return_value=[fake_suggestion]),
    ):
        result = await suggest_tool.ainvoke({"slot_id": 7})

    assert "Le Thi D" in result
    assert "2/8" in result


# ── 7. get_exam_calendar ──────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_get_exam_calendar_no_examiner(sched_ctx):
    tools = make_scheduling_tools(sched_ctx)
    cal_tool = next(t for t in tools if t.name == "get_exam_calendar")

    fake_slot = MagicMock()
    fake_slot.id = 11
    fake_slot.exam_date = "2025-08-01"
    fake_slot.start_time = "09:00"
    fake_slot.course_name = "Piano Grade 3"
    fake_slot.capacity = 10
    fake_slot.available_capacity = 5
    fake_slot.examiner_name = None

    with patch(
        "fast_api_services.services.examiner_service.get_exam_calendar",
        AsyncMock(return_value=[fake_slot]),
    ):
        result = await cal_tool.ainvoke({})

    assert "⚠️ No examiner assigned" in result
    assert "Piano Grade 3" in result


# ── 8. suggest_slots_for_reschedule ─────────────────────────────────────────

@pytest.mark.asyncio
async def test_suggest_slots_returns_list(sched_ctx):
    tools = make_reschedule_tools(sched_ctx, user_id=42)
    suggest_tool = next(t for t in tools if t.name == "suggest_slots_for_reschedule")

    fake_slot = MagicMock()
    fake_slot.id = 99
    fake_slot.center_name = "Hanoi Center"
    fake_slot.center_city = "Hanoi"
    fake_slot.exam_date = "2025-09-01"
    fake_slot.start_time = "10:00"
    fake_slot.course_name = "Guitar Grade 5"
    fake_slot.available_capacity = 3

    with patch(
        "fast_api_services.services.catalog_service.suggest_slots_for_reschedule",
        AsyncMock(return_value=[fake_slot]),
    ):
        result = await suggest_tool.ainvoke({"booking_id": 5})

    assert "Hanoi Center" in result
    assert "Guitar Grade 5" in result


@pytest.mark.asyncio
async def test_suggest_slots_empty(sched_ctx):
    tools = make_reschedule_tools(sched_ctx, user_id=42)
    suggest_tool = next(t for t in tools if t.name == "suggest_slots_for_reschedule")

    with patch(
        "fast_api_services.services.catalog_service.suggest_slots_for_reschedule",
        AsyncMock(return_value=[]),
    ):
        result = await suggest_tool.ainvoke({"booking_id": 5})

    assert "No alternative" in result
