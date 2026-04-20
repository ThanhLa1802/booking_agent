"""
SSE streaming endpoint for the Trinity AI exam assistant.

POST /api/agent/chat
  Request:  {"message": "...", "session_id": null}
  Response: text/event-stream

Event types emitted:
  {"type": "token",      "content": "..."}    — LLM output token
  {"type": "tool_start", "tool": "...", "input": "..."}
  {"type": "tool_end",   "tool": "...", "output": "..."}
  {"type": "done",       "content": "..."}    — full final response
  {"type": "error",      "content": "..."}
"""
from __future__ import annotations

import json
import logging
from typing import AsyncGenerator, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sse_starlette.sse import EventSourceResponse
from sqlalchemy.ext.asyncio import AsyncSession

from fast_api_services.auth import get_current_user
from fast_api_services.config import get_settings
from fast_api_services.database import get_db, get_session_factory

# Heavy AI imports are lazy (inside endpoint) to avoid torch/numpy BLAS crash

logger = logging.getLogger(__name__)
router = APIRouter(tags=["agent"])


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=2000)
    session_id: Optional[str] = None  # reserved for future multi-session support


class ChatResponse(BaseModel):
    type: str
    content: Optional[str] = None
    tool: Optional[str] = None
    input: Optional[str] = None
    output: Optional[str] = None


@router.post("/agent/chat")
async def chat(
    request: ChatRequest,
    current_user = Depends(get_current_user),
) -> EventSourceResponse:
    """Stream agent responses via Server-Sent Events."""
    user_id: int = current_user.user_id
    settings = get_settings()
    session_factory = get_session_factory()

    async def event_stream() -> AsyncGenerator[dict, None]:
        # ── lazy imports to avoid torch/numpy crash at module load ─────────
        from fast_api_services.agent.agent import create_agent
        from fast_api_services.agent.llm import get_embeddings, get_llm
        from fast_api_services.agent.memory import load_history, save_history
        from fast_api_services.agent.tools import ToolContext, make_tools

        # ── setup ──────────────────────────────────────────────────────────
        from fast_api_services.services.slot_cache import get_redis_client

        redis = await get_redis_client()
        embeddings = get_embeddings()
        llm = get_llm()

        ctx = ToolContext(
            session_factory=session_factory,
            redis=redis,
            user_id=user_id,
            embeddings=embeddings,
            persist_dir=settings.chroma_persist_dir,
        )
        tools = make_tools(ctx)
        chat_history = await load_history(redis, user_id)
        agent_executor = create_agent(llm, tools, chat_history)

        final_output = ""

        try:
            async for event in agent_executor.astream_events(
                {"input": request.message, "chat_history": chat_history},
                version="v2",
            ):
                kind = event.get("event", "")
                name = event.get("name", "")

                if kind == "on_chat_model_stream":
                    chunk = event.get("data", {}).get("chunk")
                    if chunk and hasattr(chunk, "content") and chunk.content:
                        token = chunk.content
                        final_output += token
                        yield {
                            "data": json.dumps({"type": "token", "content": token})
                        }

                elif kind == "on_tool_start":
                    tool_input = event.get("data", {}).get("input", "")
                    yield {
                        "data": json.dumps(
                            {
                                "type": "tool_start",
                                "tool": name,
                                "input": str(tool_input)[:200],
                            }
                        )
                    }

                elif kind == "on_tool_end":
                    tool_output = event.get("data", {}).get("output", "")
                    yield {
                        "data": json.dumps(
                            {
                                "type": "tool_end",
                                "tool": name,
                                "output": str(tool_output)[:300],
                            }
                        )
                    }

                elif kind == "on_chain_end" and name == "AgentExecutor":
                    output = event.get("data", {}).get("output", {})
                    if isinstance(output, dict):
                        final_output = output.get("output", final_output)
                    elif isinstance(output, str):
                        final_output = output

                    await save_history(redis, user_id, request.message, final_output)
                    yield {
                        "data": json.dumps({"type": "done", "content": final_output})
                    }

        except Exception as exc:
            logger.exception("Agent error for user %s: %s", user_id, exc)
            yield {"data": json.dumps({"type": "error", "content": str(exc)})}

    return EventSourceResponse(event_stream())
