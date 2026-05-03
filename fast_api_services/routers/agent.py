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
import re
from typing import AsyncGenerator, Optional
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field, field_validator
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

    #validate message content for safety (basic example, can be expanded with more robust checks)
    @field_validator("message")
    @classmethod
    def validate_message(cls, v):
        dangerous = [r"ignore.*instruction", r"system.*override", r"bypass.*confirmation"]
        for pattern in dangerous:
            if re.search(pattern, v, re.IGNORECASE):
                raise ValueError("Invalid message")
        return v

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
        from fast_api_services.agent.memory import (
            clear_pending_proposal,
            load_history,
            load_pending_proposal,
            save_history,
            save_pending_proposal,
        )
        from fast_api_services.agent.scheduling_tools import (
            SchedulingToolContext,
            make_reschedule_tools,
            make_scheduling_tools,
        )
        from fast_api_services.agent.supervisor import create_supervisor_graph
        from fast_api_services.agent.tools import ToolContext, make_tools
        from fast_api_services.services.slot_cache import get_redis_client

        # ── setup ──────────────────────────────────────────────────────────
        redis = await get_redis_client()
        embeddings = get_embeddings()
        llm = get_llm()

        # ── resolve user_role from DB ──────────────────────────────────────
        user_role = "STUDENT"
        center_id = 0
        try:
            async with session_factory() as db:
                from sqlalchemy import select, text
                # Query user profile to get role and find associated center
                query = text("""
                    SELECT up.role, ec.id AS center_id
                    FROM accounts_userprofile up
                    LEFT JOIN centers_examcenter ec 
                        ON ec.admin_user_id = up.user_id
                    WHERE up.user_id = :uid
                """)
                result = await db.execute(query, {"uid": user_id})
                profile = result.fetchone()
                if profile:
                    role_val = profile[0]       # profile.role
                    center_id = profile[1] or 0 # profile.center_id
                    # Use explicit role if set; if admin center but no explicit role, mark CENTER_ADMIN
                    user_role = role_val if role_val else (
                        "CENTER_ADMIN" if center_id > 0 else "STUDENT"
                    )
        except Exception as exc:
            logger.warning("Could not fetch user_role for %s: %s", user_id, exc)

        ctx = ToolContext(
            session_factory=session_factory,
            redis=redis,
            user_id=user_id,
            user_token=current_user.raw_token,
            embeddings=embeddings,
            persist_dir=settings.chroma_persist_dir,
            user_role=user_role,
        )
        booking_tools = make_tools(ctx)
        chat_history = await load_history(redis, user_id)

        # ── pending proposal (scheduling confirmation gate) ────────────────
        _CONFIRM_KW = {"xác nhận", "yes", "đồng ý", "confirm", "ok", "có"}
        _CANCEL_KW = {"hủy", "no", "không", "cancel"}
        msg_lower = request.message.strip().lower()
        is_confirmation = any(kw in msg_lower for kw in _CONFIRM_KW)
        is_cancel = any(kw in msg_lower for kw in _CANCEL_KW)

        pending_proposal = await load_pending_proposal(redis, user_id)
        if pending_proposal and is_cancel:
            await clear_pending_proposal(redis, user_id)
            pending_proposal = None

        sched_ctx = SchedulingToolContext(
            session_factory=session_factory,
            user_token=current_user.raw_token,
            center_id=center_id,
        )
        scheduling_tools = (
            make_scheduling_tools(sched_ctx)
            + make_reschedule_tools(sched_ctx, user_id)
        )

        supervisor = create_supervisor_graph(
            booking_tools=booking_tools,
            scheduling_tools=scheduling_tools,
            llm=llm,
            chat_history=chat_history,
        )

        from langchain_core.messages import HumanMessage

        _resume = bool(pending_proposal and is_confirmation)

        # ── early "please wait" feedback for batch scheduling ──────────────
        # batch scheduling takes 15+ s (Celery task + Redis polling).
        # Yield a status token immediately so the admin sees feedback.
        import re as _batch_re
        _is_batch_sched = (
            not _resume
            and user_role == "CENTER_ADMIN"
            and _batch_re.search(r"xếp lịch|lập lịch", request.message, _batch_re.IGNORECASE)
            and _batch_re.search(r"tháng|tuần|month|week|\d{4}-\d{2}-\d{2}", request.message, _batch_re.IGNORECASE)
        )
        if _is_batch_sched:
            yield {"data": json.dumps({"type": "token", "content": "⏳ Đang xếp lịch, vui lòng đợi trong giây lát..."})}

        initial_state = {
            "messages": [HumanMessage(content=request.message)],
            "user_role": user_role,
            "task_type": pending_proposal["task_type"] if _resume else "general",
            "proposal": pending_proposal["proposal"] if _resume else None,
            "confirmed": True if _resume else False,
            "thread_id": str(user_id),
        }

        final_output = ""

        try:
            # ── Confirmation turn: execute_node doesn't call LLM, so no stream tokens.
            # Use ainvoke directly to get a reliable result instead of astream_events.
            if _resume:
                result = await supervisor.ainvoke(
                    initial_state,
                    config={"configurable": {"thread_id": str(user_id)}},
                )
                msgs = result.get("messages", [])
                if msgs:
                    final_output = getattr(msgs[-1], "content", "")
                # Clear the pending proposal after execution
                await clear_pending_proposal(redis, user_id)
                await save_history(redis, user_id, request.message, final_output)
                yield {"data": json.dumps({"type": "done", "content": final_output})}
                return

            async for event in supervisor.astream_events(
                initial_state,
                version="v2",
                config={"configurable": {"thread_id": str(user_id)}},
            ):
                kind = event.get("event", "")
                name = event.get("name", "")

                # Internal nodes whose LLM output must NOT reach the user
                _INTERNAL_NODES = {"classify_node", "fetch_node"}

                if kind == "on_chat_model_stream":
                    node_name = event.get("metadata", {}).get("langgraph_node", "")
                    if node_name in _INTERNAL_NODES:
                        pass  # skip internal classification/routing tokens
                    else:
                        chunk = event.get("data", {}).get("chunk")
                        if chunk and hasattr(chunk, "content") and chunk.content:
                            token = chunk.content
                            final_output += token
                            yield {
                                "data": json.dumps({"type": "token", "content": token})
                            }

                elif kind == "on_tool_start":
                    node_name = event.get("metadata", {}).get("langgraph_node", "")
                    if node_name not in _INTERNAL_NODES:
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
                    node_name = event.get("metadata", {}).get("langgraph_node", "")
                    if node_name not in _INTERNAL_NODES:
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

                elif kind == "on_chain_end":
                    output = event.get("data", {}).get("output", {})
                    if isinstance(output, dict):
                        # Save/clear proposal based on scheduling_subgraph output.
                        # We check the subgraph node (registered in SupervisorGraph)
                        # rather than the inner propose_node, because ainvoke() on a
                        # nested compiled graph does not always surface inner node
                        # names reliably in astream_events.
                        if name == "scheduling_subgraph":
                            proposal_out = output.get("proposal")
                            confirmed_out = output.get("confirmed", False)
                            if proposal_out and not confirmed_out:
                                # Proposal made, waiting for user confirmation
                                p_msgs = output.get("messages", [])
                                p_text = p_msgs[-1].content if p_msgs else ""
                                await save_pending_proposal(
                                    redis,
                                    user_id,
                                    proposal_out.get("task_type", "general"),
                                    proposal_out,
                                    p_text,
                                )
                            else:
                                # Executed, cancelled, or read-only — clear any pending proposal
                                await clear_pending_proposal(redis, user_id)

                        msgs = output.get("messages", [])
                        if msgs:
                            last = msgs[-1]
                            final_output = getattr(last, "content", final_output)

            await save_history(redis, user_id, request.message, final_output)
            yield {"data": json.dumps({"type": "done", "content": final_output})}

        except Exception as exc:
            logger.exception("Agent error for user %s: %s", user_id, exc)
            yield {"data": json.dumps({"type": "error", "content": str(exc)})}

    return EventSourceResponse(event_stream())
