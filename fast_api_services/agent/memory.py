"""
Redis-backed conversation history for the LangChain agent.

Key: session:{user_id}
Value: JSON list of {"type": "human"|"ai", "content": "..."}
TTL: 1800 seconds (30 min)
"""
from __future__ import annotations

import json
import logging
from typing import Any

logger = logging.getLogger(__name__)

_HISTORY_TTL = 1800  # 30 minutes


def _redis_key(user_id: int) -> str:
    return f"session:{user_id}"


def _serialize(messages: list) -> str:
    data = [{"type": m.type, "content": m.content} for m in messages]
    return json.dumps(data)


def _deserialize(raw: str) -> list:
    from langchain_core.messages import AIMessage, HumanMessage
    items: list[dict[str, Any]] = json.loads(raw)
    messages: list = []
    for item in items:
        if item.get("type") == "human":
            messages.append(HumanMessage(content=item["content"]))
        elif item.get("type") == "ai":
            messages.append(AIMessage(content=item["content"]))
    return messages


async def load_history(redis, user_id: int) -> list:
    """Load conversation history from Redis. Returns empty list if none."""
    try:
        raw = await redis.get(_redis_key(user_id))
        if raw is None:
            return []
        return _deserialize(raw if isinstance(raw, str) else raw.decode())
    except Exception as exc:
        logger.error("Failed to load history for user %s: %s", user_id, exc)
        return []


async def save_history(
    redis,
    user_id: int,
    human_msg: str,
    ai_msg: str,
    ttl: int = _HISTORY_TTL,
) -> None:
    """Append the latest turn and persist back to Redis."""
    from langchain_core.messages import AIMessage, HumanMessage
    existing = await load_history(redis, user_id)
    existing.append(HumanMessage(content=human_msg))
    existing.append(AIMessage(content=ai_msg))
    try:
        await redis.setex(_redis_key(user_id), ttl, _serialize(existing))
    except Exception as exc:
        logger.error("Failed to save history for user %s: %s", user_id, exc)


async def clear_history(redis, user_id: int) -> None:
    """Delete conversation history (e.g. on explicit reset)."""
    try:
        await redis.delete(_redis_key(user_id))
    except Exception as exc:
        logger.error("Failed to clear history for user %s: %s", user_id, exc)
