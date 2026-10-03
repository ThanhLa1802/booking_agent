"""
Tests for the server-side write-authorization boundary (P0).

The LLM's confirm=True must NOT be sufficient when the context is
server-managed — only a hash pre-authorized by the router passes.
"""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from fast_api_services.agent.authorization import action_hash, authorize_write
from fast_api_services.agent.tools import _CONFIRM_REQUIRED, ToolContext, make_tools


def _managed_ctx(allowed: frozenset = frozenset()) -> MagicMock:
    ctx = MagicMock(spec=ToolContext)
    ctx.redis = AsyncMock()
    ctx.user_id = 42
    ctx.user_token = "test.jwt.token"
    ctx.session_factory = MagicMock()
    ctx.embeddings = MagicMock()
    ctx.persist_dir = "./test_chroma"
    ctx.user_role = "STUDENT"
    ctx.authorized_actions = allowed
    return ctx


class TestActionHash:
    def test_deterministic(self):
        args = {"slot_id": 5, "student_name": "A"}
        assert action_hash("create_booking", args) == action_hash("create_booking", args)

    def test_ignores_confirm_flag(self):
        args = {"slot_id": 5}
        assert action_hash("create_booking", {**args, "confirm": False}) == action_hash(
            "create_booking", {**args, "confirm": True}
        )

    def test_differs_by_args(self):
        assert action_hash("create_booking", {"slot_id": 1}) != action_hash(
            "create_booking", {"slot_id": 2}
        )


class TestAuthorizeWrite:
    @pytest.mark.asyncio
    async def test_unmanaged_ctx_falls_back_to_confirm(self):
        ctx = MagicMock(spec=ToolContext)  # authorized_actions is a MagicMock
        assert await authorize_write(ctx, "create_booking", {"slot_id": 1}, True) is True
        assert await authorize_write(ctx, "create_booking", {"slot_id": 1}, False) is False

    @pytest.mark.asyncio
    async def test_managed_ctx_blocks_without_hash(self):
        ctx = _managed_ctx(frozenset())
        assert await authorize_write(ctx, "create_booking", {"slot_id": 1}, True) is False

    @pytest.mark.asyncio
    async def test_managed_ctx_allows_matching_hash(self):
        args = {"slot_id": 1}
        ctx = _managed_ctx(frozenset({action_hash("create_booking", args)}))
        assert await authorize_write(ctx, "create_booking", args, True) is True


class TestToolLevelBoundary:
    @pytest.mark.asyncio
    async def test_create_booking_confirm_true_still_blocked(self):
        """Even with confirm=True, a server-managed ctx without the hash refuses."""
        tools = make_tools(_managed_ctx())
        create = next(t for t in tools if t.name == "create_booking")

        result = await create.ainvoke(
            {
                "slot_id": 5,
                "student_name": "Le Thi B",
                "student_dob": "2012-06-15",
                "notes": "",
                "confirm": True,
            }
        )

        assert _CONFIRM_REQUIRED in result

    @pytest.mark.asyncio
    async def test_create_booking_executes_when_authorized(self):
        args = {
            "slot_id": 5,
            "student_name": "Le Thi B",
            "student_dob": "2012-06-15",
            "notes": "needs piano",
        }
        ctx = _managed_ctx(frozenset({action_hash("create_booking", args)}))
        tools = make_tools(ctx)
        create = next(t for t in tools if t.name == "create_booking")

        mock_response = MagicMock()
        mock_response.status_code = 201
        mock_response.json.return_value = {"id": 123}

        with patch("fast_api_services.agent.tools.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client_cls.return_value = mock_client

            result = await create.ainvoke({**args, "confirm": True})

        assert "123" in result


class TestPendingActionStore:
    @pytest.mark.asyncio
    async def test_save_load_clear(self, fake_redis):
        from fast_api_services.agent.memory import (
            clear_pending_action,
            load_pending_action,
            save_pending_action,
        )

        await save_pending_action(fake_redis, 42, "create_booking", {"slot_id": 1}, "h1")
        loaded = await load_pending_action(fake_redis, 42)
        assert loaded["tool"] == "create_booking"
        assert loaded["hash"] == "h1"

        await clear_pending_action(fake_redis, 42)
        assert await load_pending_action(fake_redis, 42) is None
