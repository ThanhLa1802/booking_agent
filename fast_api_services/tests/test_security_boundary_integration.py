"""
Integration tests for the server-side write gate across agent paths.

These lock in the invariant that *every* write tool is backed by the
server-managed authorization set, not the model's ``confirm`` flag.

Two tests are marked xfail because the current wiring leaves gaps; they turn
green once:
  * the router authorizes the action implied by a confirmed scheduling proposal
    (routers/agent.py derives ``authorized_actions`` from ``pending_action``
    only, but ``propose_node`` never records one), and
  * the booking graph forwards its managed context to the reschedule tools
    (tools.py builds them with an unmanaged ``SchedulingToolContext``).
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from fast_api_services.agent.authorization import action_hash
from fast_api_services.agent.scheduling_tools import (
    SchedulingToolContext,
    make_reschedule_tools,
    make_scheduling_tools,
)
from fast_api_services.agent.scheduling_tools import (
    _CONFIRM_REQUIRED as SCHED_CONFIRM,
)
from fast_api_services.agent.tools import (
    _CONFIRM_REQUIRED,
    ToolContext,
    make_tools,
)


def _session_factory():
    sm = MagicMock()
    sm.return_value = MagicMock()
    sm.return_value.__aenter__ = AsyncMock(return_value=AsyncMock())
    sm.return_value.__aexit__ = AsyncMock(return_value=False)
    return sm


def _sched_ctx(allowed: frozenset) -> SchedulingToolContext:
    return SchedulingToolContext(
        session_factory=_session_factory(),
        user_token="test.jwt.token",
        center_id=1,
        user_id=42,
        redis=AsyncMock(),
        authorized_actions=allowed,
    )


def _booking_ctx(allowed: frozenset) -> ToolContext:
    return ToolContext(
        session_factory=_session_factory(),
        redis=AsyncMock(),
        user_id=42,
        user_token="test.jwt.token",
        embeddings=MagicMock(),
        persist_dir="./test_chroma",
        authorized_actions=allowed,
    )


def _httpx_ok(json_body):
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = json_body
    return mock_response


def _patch_httpx(json_body):
    """Patch httpx.AsyncClient so the tool's HTTP call is captured, not sent."""
    ctx = patch("httpx.AsyncClient")
    cls = ctx.start()
    client = AsyncMock()
    client.post = AsyncMock(return_value=_httpx_ok(json_body))
    cls.return_value.__aenter__ = AsyncMock(return_value=client)
    cls.return_value.__aexit__ = AsyncMock(return_value=False)
    return ctx


class TestAdminSchedulingGate:
    @pytest.mark.asyncio
    async def test_assign_blocked_without_server_authorization(self):
        tools = make_scheduling_tools(_sched_ctx(frozenset()))
        tool = next(t for t in tools if t.name == "assign_examiner_to_slot")

        result = await tool.ainvoke({"slot_id": 5, "examiner_id": 2, "confirm": True})

        assert SCHED_CONFIRM in result

    @pytest.mark.asyncio
    async def test_assign_executes_with_matching_hash(self):
        args = {"slot_id": 5, "examiner_id": 2}
        ctx = _sched_ctx(frozenset({action_hash("assign_examiner_to_slot", args)}))
        tools = make_scheduling_tools(ctx)
        tool = next(t for t in tools if t.name == "assign_examiner_to_slot")

        patcher = _patch_httpx({"examiner_name": "Nguyen Thi B"})
        try:
            result = await tool.ainvoke({**args, "confirm": True})
        finally:
            patcher.stop()

        assert "✅" in result

    @pytest.mark.asyncio
    async def test_admin_reschedule_blocked_without_server_authorization(self):
        tools = make_reschedule_tools(_sched_ctx(frozenset()), user_id=42)
        tool = next(t for t in tools if t.name == "reschedule_booking")

        result = await tool.ainvoke(
            {"booking_id": 10, "new_slot_id": 20, "reason": "x", "confirm": True}
        )

        assert SCHED_CONFIRM in result

    @pytest.mark.xfail(
        reason="propose_node never records a pending_action, so on the resume turn "
        "the router supplies an empty authorized set and execute_node's write is "
        "refused (routers/agent.py derives authorized_actions from pending_action only)",
        strict=False,
    )
    @pytest.mark.asyncio
    async def test_resume_turn_authorizes_proposal_implied_action(self):
        # Production resume wiring: pending_proposal exists, pending_action does
        # not -> authorized_actions == frozenset().
        ctx = _sched_ctx(frozenset())
        tools = make_scheduling_tools(ctx)
        tool = next(t for t in tools if t.name == "assign_examiner_to_slot")

        patcher = _patch_httpx({"examiner_name": "X"})
        try:
            result = await tool.ainvoke(
                {"slot_id": 5, "examiner_id": 2, "confirm": True}
            )
        finally:
            patcher.stop()

        assert SCHED_CONFIRM not in result


class TestBookingGraphGate:
    @pytest.mark.xfail(
        reason="make_tools builds the reschedule tools with an unmanaged "
        "SchedulingToolContext (tools.py), so reschedule_booking falls back to "
        "the model's confirm flag instead of the server-managed set",
        strict=False,
    )
    @pytest.mark.asyncio
    async def test_student_reschedule_uses_server_managed_gate(self):
        tools = make_tools(_booking_ctx(frozenset()))
        tool = next(t for t in tools if t.name == "reschedule_booking")

        patcher = _patch_httpx({"slot": 20})
        try:
            result = await tool.ainvoke(
                {"booking_id": 10, "new_slot_id": 20, "reason": "x", "confirm": True}
            )
        finally:
            patcher.stop()

        assert _CONFIRM_REQUIRED in result
