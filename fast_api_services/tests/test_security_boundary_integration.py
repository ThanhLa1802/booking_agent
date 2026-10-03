"""
Integration tests for the server-side write gate across agent paths.

These lock in the invariant that *every* write tool is backed by the
server-managed authorization set, not the model's ``confirm`` flag:

  * a write with no server authorization is refused even at ``confirm=True``;
  * a matching hash (from a ``pending_action`` or a confirmed scheduling
    proposal) lets it through;
  * the router's ``compute_authorized_actions`` is the single source of that set.
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from fast_api_services.agent.authorization import action_hash
from fast_api_services.agent.proposals import proposal_to_action
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
from fast_api_services.agent.write_gate import compute_authorized_actions


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

    @pytest.mark.asyncio
    async def test_resume_turn_authorizes_proposal_implied_action(self):
        # The router authorizes the action implied by a confirmed proposal.
        proposal = {
            "task_type": "assign_examiner",
            "slot_id": 5,
            "examiner_id": 2,
            "conversation_messages": [],
        }
        tool_name, args = proposal_to_action(proposal)
        assert tool_name == "assign_examiner_to_slot"

        allowed = compute_authorized_actions(
            pending_action=None,
            pending_proposal={"proposal": proposal},
            is_confirm_msg=True,
        )
        assert action_hash(tool_name, args) in allowed

        tools = make_scheduling_tools(_sched_ctx(allowed))
        tool = next(t for t in tools if t.name == tool_name)
        patcher = _patch_httpx({"examiner_name": "X"})
        try:
            result = await tool.ainvoke({**args, "confirm": True})
        finally:
            patcher.stop()

        assert SCHED_CONFIRM not in result

    @pytest.mark.asyncio
    async def test_confirm_schedule_plan_blocked_without_authorization(self):
        tools = make_scheduling_tools(_sched_ctx(frozenset()))
        tool = next(t for t in tools if t.name == "confirm_schedule_plan")

        result = await tool.ainvoke({"task_id": "abc-123", "confirm": True})

        assert SCHED_CONFIRM in result

    @pytest.mark.asyncio
    async def test_confirm_schedule_plan_executes_with_proposal_authorization(self):
        proposal = {"task_type": "batch_assign", "task_id": "abc-123"}
        tool_name, args = proposal_to_action(proposal)
        assert tool_name == "confirm_schedule_plan"

        allowed = compute_authorized_actions(None, {"proposal": proposal}, True)
        tools = make_scheduling_tools(_sched_ctx(allowed))
        tool = next(t for t in tools if t.name == "confirm_schedule_plan")

        patcher = _patch_httpx({"assigned_count": 12})
        try:
            result = await tool.ainvoke({**args, "confirm": True})
        finally:
            patcher.stop()

        assert "✅" in result


class TestBookingGraphGate:
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


class TestComputeAuthorizedActions:
    def test_empty_without_confirmation(self):
        proposal = {"task_type": "assign_examiner", "slot_id": 5, "examiner_id": 2}
        assert compute_authorized_actions(None, {"proposal": proposal}, False) == frozenset()

    def test_includes_pending_action_hash(self):
        allowed = compute_authorized_actions({"hash": "deadbeef"}, None, True)
        assert "deadbeef" in allowed

    def test_includes_proposal_action_hash(self):
        proposal = {"task_type": "batch_assign", "task_id": "t1"}
        allowed = compute_authorized_actions(None, {"proposal": proposal}, True)
        assert action_hash("confirm_schedule_plan", {"task_id": "t1"}) in allowed

    def test_ignores_unknown_task_type(self):
        proposal = {"task_type": "general"}
        assert compute_authorized_actions(None, {"proposal": proposal}, True) == frozenset()
