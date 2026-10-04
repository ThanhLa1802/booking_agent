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

from fast_api_services.auth import get_current_user
from fast_api_services.config import get_settings
from fast_api_services.database import get_session_factory

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
        from fast_api_services.agent.confirmation import is_cancel, is_confirmation
        from fast_api_services.agent.llm import get_embeddings, get_llm
        from fast_api_services.agent.memory import (
            clear_pending_action,
            clear_pending_proposal,
            load_history,
            load_pending_action,
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
        from fast_api_services.agent.write_gate import compute_authorized_actions
        from fast_api_services.services.slot_cache import get_redis_client

        # ── setup ──────────────────────────────────────────────────────────
        redis = await get_redis_client()
        embeddings = get_embeddings()
        llm = get_llm()

        # ── resolve user_role from DB ──────────────────────────────────────
        user_role = "STUDENT"
        center_id = 0
        examiner_id: Optional[int] = None
        try:
            async with session_factory() as db:
                from sqlalchemy import text
                # Query user profile to get role, associated center and linked examiner
                query = text("""
                    SELECT up.role, ec.id AS center_id, ex.id AS examiner_id
                    FROM accounts_userprofile up
                    LEFT JOIN centers_examcenter ec 
                        ON ec.admin_user_id = up.user_id
                    LEFT JOIN centers_examiner ex
                        ON ex.user_id = up.user_id
                    WHERE up.user_id = :uid
                """)
                result = await db.execute(query, {"uid": user_id})
                profile = result.fetchone()
                if profile:
                    role_val = profile[0]       # profile.role
                    center_id = profile[1] or 0 # profile.center_id
                    examiner_id = profile[2]    # linked examiner id (EXAMINER only)
                    # Use explicit role if set; if admin center but no explicit role, mark CENTER_ADMIN
                    user_role = role_val if role_val else (
                        "CENTER_ADMIN" if center_id > 0 else "STUDENT"
                    )
        except Exception as exc:
            logger.warning("Could not fetch user_role for %s: %s", user_id, exc)

        # ── deterministic scope/role guard (before any LLM call) ───────────
        # Clear role-escalation / off-topic requests are refused here without
        # invoking the model (see agent/scope_guard.py). Not a write boundary.
        from fast_api_services.agent.scope_guard import classify_scope

        scope = classify_scope(request.message, user_role)
        if scope is not None:
            await save_history(redis, user_id, request.message, scope.reply)
            yield {"data": json.dumps({"type": "done", "content": scope.reply})}
            return

        # ── confirmation signals (explicit, standalone commands only) ──────
        is_confirm_msg = is_confirmation(request.message)
        is_cancel_msg = is_cancel(request.message)

        pending_proposal = await load_pending_proposal(redis, user_id)
        if pending_proposal and is_cancel_msg:
            await clear_pending_proposal(redis, user_id)
            pending_proposal = None

        # A stored scheduling proposal confirmed this turn resumes directly.
        _resume = bool(pending_proposal and is_confirm_msg)

        # ── server-side write authorization ────────────────────────────────
        # A write only executes if the user's RAW message is an explicit
        # confirmation AND it matches a pending action recorded on a prior turn
        # or the write implied by a stored scheduling proposal.
        pending_action = await load_pending_action(redis, user_id)
        if pending_action and is_cancel_msg:
            await clear_pending_action(redis, user_id)
            pending_action = None
        authorized_actions = compute_authorized_actions(
            pending_action, pending_proposal, is_confirm_msg
        )

        ctx = ToolContext(
            session_factory=session_factory,
            redis=redis,
            user_id=user_id,
            user_token=current_user.raw_token,
            embeddings=embeddings,
            persist_dir=settings.chroma_persist_dir,
            user_role=user_role,
            authorized_actions=authorized_actions,
        )
        # Least privilege: only build the tools the caller's role can actually
        # use. A student/parent never gets admin/scheduling tools; an admin
        # never gets the booking toolset.
        booking_tools = (
            make_tools(ctx)
            if user_role not in ("CENTER_ADMIN", "EXAMINER")
            else []
        )
        chat_history = await load_history(redis, user_id)

        sched_ctx = SchedulingToolContext(
            session_factory=session_factory,
            user_token=current_user.raw_token,
            center_id=center_id,
            user_id=user_id,
            redis=redis,
            authorized_actions=authorized_actions,
        )
        scheduling_tools = (
            make_scheduling_tools(sched_ctx)
            + make_reschedule_tools(sched_ctx, user_id)
            if user_role == "CENTER_ADMIN"
            else []
        )

        # ── examiner tools (read-only, own schedule only) ──────────────────
        examiner_tools: list = []
        if user_role == "EXAMINER":
            from fast_api_services.agent.examiner_tools import (
                ExaminerToolContext,
                make_examiner_tools,
            )

            examiner_ctx = ExaminerToolContext(
                session_factory=session_factory,
                examiner_id=examiner_id,
                user_id=user_id,
                redis=redis,
            )
            examiner_tools = make_examiner_tools(examiner_ctx)

        supervisor = create_supervisor_graph(
            booking_tools=booking_tools,
            scheduling_tools=scheduling_tools,
            llm=llm,
            chat_history=chat_history,
            examiner_tools=examiner_tools,
        )

        from langchain_core.messages import HumanMessage

        # ── early "please wait" feedback for batch scheduling ──────────────
        # batch scheduling takes 15+ s (Celery task + Redis polling).
        # Yield a status token immediately so the admin sees feedback.
        _is_batch_sched = (
            not _resume
            and user_role == "CENTER_ADMIN"
            and re.search(r"xếp lịch|lập lịch", request.message, re.IGNORECASE)
            and re.search(r"tháng|tuần|month|week|\d{4}-\d{2}-\d{2}", request.message, re.IGNORECASE)
        )
        if _is_batch_sched:
            yield {"data": json.dumps({"type": "token", "content": "⏳ Đang xếp lịch, vui lòng đợi trong giây lát..."})}

        if _resume and pending_proposal is not None:
            resume_task_type = pending_proposal["task_type"]
            resume_proposal = pending_proposal["proposal"]
        else:
            resume_task_type = "general"
            resume_proposal = None

        initial_state = {
            "messages": [HumanMessage(content=request.message)],
            "user_role": user_role,
            "task_type": resume_task_type,
            "proposal": resume_proposal,
            "confirmed": True if _resume else False,
            "thread_id": str(user_id),
        }

        final_output = ""
        tool_outputs: list[str] = []

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
                if is_confirm_msg:
                    await clear_pending_action(redis, user_id)
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
                        tool_outputs.append(str(tool_output))
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

            # ── grounding guard: flag numbers absent from tool output ──────
            if getattr(settings, "grounding_guard_enabled", True):
                from fast_api_services.agent.grounding import find_ungrounded_numbers

                ungrounded = find_ungrounded_numbers(final_output, tool_outputs)
                if ungrounded:
                    logger.warning(
                        "Grounding guard: ungrounded numbers %s for user %s",
                        ungrounded,
                        user_id,
                    )
                    if getattr(settings, "grounding_guard_strict", False):
                        final_output = (
                            "Xin lỗi, tôi cần kiểm tra lại thông tin để đảm bảo "
                            "chính xác. Vui lòng thử lại hoặc liên hệ trung tâm."
                        )

            await save_history(redis, user_id, request.message, final_output)
            # Consume the confirmation only once a write actually executed.
            # A refused confirm (no/mismatched pending action) must NOT delete the
            # pending action, otherwise a re-registered action gets erased and the
            # user can never confirm — an infinite "please confirm again" loop.
            if is_confirm_msg and any("✅" in out for out in tool_outputs):
                await clear_pending_action(redis, user_id)
            yield {"data": json.dumps({"type": "done", "content": final_output})}

        except Exception as exc:
            logger.exception("Agent error for user %s: %s", user_id, exc)
            # Never leave the user with an empty reply: if nothing was streamed
            # (e.g. a tool raised on bad arguments), send a graceful message.
            if not final_output:
                final_output = (
                    "Xin lỗi, mình gặp sự cố khi xử lý yêu cầu này. "
                    "Vui lòng thử lại hoặc diễn đạt lại giúp mình."
                )
                yield {"data": json.dumps({"type": "done", "content": final_output})}
            else:
                yield {"data": json.dumps({"type": "error", "content": str(exc)})}

    return EventSourceResponse(event_stream())
