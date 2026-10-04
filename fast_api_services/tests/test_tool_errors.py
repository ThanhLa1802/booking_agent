"""
Tool argument errors must become observations, not crash the agent turn.

Regression for the case where the model calls a tool with missing arguments
(e.g. ``list_available_slots`` without ``course_id``): the pydantic
ValidationError used to abort the turn and yield an empty reply. With
``harden_tools`` it is returned to the model as an observation so it can retry.
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from fast_api_services.agent.tools import ToolContext, make_tools


def _ctx() -> ToolContext:
    sm = MagicMock()
    sm.return_value = MagicMock()
    sm.return_value.__aenter__ = AsyncMock(return_value=AsyncMock())
    sm.return_value.__aexit__ = AsyncMock(return_value=False)
    return ToolContext(
        session_factory=sm,
        redis=AsyncMock(),
        user_id=1,
        user_token="test.jwt.token",
        embeddings=MagicMock(),
        persist_dir="./chroma_test",
        authorized_actions=frozenset(),
    )


@pytest.mark.asyncio
async def test_missing_required_arg_becomes_observation_not_exception():
    tools = make_tools(_ctx())
    tool = next(t for t in tools if t.name == "list_available_slots")

    result = await tool.ainvoke({})  # missing required course_id

    assert "Tool argument error" in str(result)
