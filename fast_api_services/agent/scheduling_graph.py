"""
SchedulingGraph — LangGraph StateGraph for CENTER_ADMIN exam scheduling.

Graph topology:
    START → classify_node → fetch_node → propose_node
                                              │
                              ┌───────────────┴───────────────┐
                         (view_calendar             (assign / reschedule)
                          or general)                    ↓
                              │                    confirm_node ──(yes)──→ execute_node → END
                              └────────────────────────(no)──→ END (agent asks user)
"""
from __future__ import annotations

import json
import logging
from typing import Any

import httpx
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from fast_api_services.config import get_settings

from .state import SchedulingState

logger = logging.getLogger(__name__)


# ── node: classify ────────────────────────────────────────────────────────────

def _make_classify_node(llm):
    async def classify_node(state: SchedulingState) -> dict:
        """
        Use the LLM to classify the admin's intent into one of:
          assign_examiner | view_calendar | reschedule | general
        """
        last_human = next(
            (m for m in reversed(state["messages"]) if isinstance(m, HumanMessage)),
            None,
        )
        if not last_human:
            return {"task_type": "general", "proposal": None, "confirmed": False}

        classification_prompt = SystemMessage(
            content=(
                "Classify the following CENTER_ADMIN message into exactly one of these task types:\n"
                "  assign_examiner  — assigning or changing which examiner covers a slot\n"
                "  view_calendar    — viewing the exam schedule or calendar\n"
                "  reschedule       — rescheduling a student's booking to a new slot\n"
                "  general          — anything else (questions, greetings, etc.)\n\n"
                "Respond with ONLY the task_type string, nothing else."
            )
        )
        response = await llm.ainvoke([classification_prompt, last_human])
        task_type = response.content.strip().lower()
        if task_type not in ("assign_examiner", "view_calendar", "reschedule", "general"):
            task_type = "general"
        return {"task_type": task_type, "proposal": None, "confirmed": False}

    return classify_node


# ── node: fetch ───────────────────────────────────────────────────────────────

def _make_fetch_node(tools: list):
    """Run the appropriate read-only tool to gather data needed for the proposal."""
    tool_map = {t.name: t for t in tools}

    async def fetch_node(state: SchedulingState) -> dict:
        last_human = next(
            (m for m in reversed(state["messages"]) if isinstance(m, HumanMessage)),
            None,
        )
        user_msg = last_human.content if last_human else ""
        task_type = state.get("task_type", "general")
        fetched_text = ""

        if task_type == "view_calendar":
            tool = tool_map.get("get_exam_calendar")
            if tool:
                fetched_text = await tool.ainvoke({})
        elif task_type == "assign_examiner":
            # Try to extract slot_id from the message
            tool = tool_map.get("get_exam_calendar")
            if tool:
                fetched_text = await tool.ainvoke({})
        elif task_type == "reschedule":
            # For reschedule we just summarise — let propose_node do the heavy lifting
            fetched_text = f"Received reschedule request: {user_msg}"

        if fetched_text:
            return {"messages": [AIMessage(content=f"[FETCH] {fetched_text}")]}
        return {}

    return fetch_node


# ── node: propose ─────────────────────────────────────────────────────────────

def _make_propose_node(llm, tools: list):
    """Generate a clear natural-language proposal for the admin to confirm."""
    tool_map = {t.name: t for t in tools}

    async def propose_node(state: SchedulingState) -> dict:
        task_type = state.get("task_type", "general")

        # For view_calendar and general, no confirmation needed — just reply directly
        if task_type in ("view_calendar", "general"):
            # Summarise the fetched data using the LLM
            response = await llm.ainvoke(state["messages"])
            return {
                "messages": [AIMessage(content=response.content)],
                "proposal": None,
                "confirmed": True,   # no confirmation needed for reads
            }

        # For write operations, build a structured proposal
        last_human = next(
            (m for m in reversed(state["messages"]) if isinstance(m, HumanMessage)),
            None,
        )
        system = SystemMessage(
            content=(
                "You are a scheduling assistant. Based on the conversation and fetched data, "
                "create a clear, concise action proposal in Vietnamese that the admin needs to confirm.\n"
                "Format:\n"
                "🗓️ **Đề xuất hành động:**\n"
                "<detail>\n\n"
                "Reply 'xác nhận' to proceed or 'hủy' to cancel."
            )
        )
        response = await llm.ainvoke([system] + state["messages"])
        proposal_text = response.content

        # Store structured proposal for execute_node
        proposal = {
            "task_type": task_type,
            "description": proposal_text,
            # extract slot/examiner IDs from context if possible — execute_node re-parses
        }
        return {
            "messages": [AIMessage(content=proposal_text)],
            "proposal": proposal,
            "confirmed": False,
        }

    return propose_node


# ── node: confirm ─────────────────────────────────────────────────────────────

_CONFIRM_KEYWORDS = {"xác nhận", "yes", "đồng ý", "confirm", "ok", "có"}


async def confirm_node(state: SchedulingState) -> dict:
    """
    Check the latest human message for an explicit confirmation.
    If confirmed → set confirmed=True.
    If rejected (hủy / no / không) → clear proposal.
    Otherwise → ask again (interrupt).
    """
    last_human = next(
        (m for m in reversed(state["messages"]) if isinstance(m, HumanMessage)),
        None,
    )
    if not last_human:
        return {}

    text = last_human.content.strip().lower()

    if any(kw in text for kw in _CONFIRM_KEYWORDS):
        return {"confirmed": True}

    if any(kw in text for kw in {"hủy", "no", "không", "cancel"}):
        return {
            "messages": [AIMessage(content="❌ Hành động đã bị hủy.")],
            "proposal": None,
            "confirmed": False,
        }

    # Not a clear answer — ask again
    return {
        "messages": [
            AIMessage(
                content="Vui lòng trả lời 'xác nhận' để tiếp tục hoặc 'hủy' để hủy bỏ."
            )
        ],
        "confirmed": False,
    }


# ── node: execute ─────────────────────────────────────────────────────────────

def _make_execute_node(tools: list):
    """Call the appropriate write tool with confirm=True after user confirmation."""
    tool_map = {t.name: t for t in tools}

    async def execute_node(state: SchedulingState) -> dict:
        proposal = state.get("proposal") or {}
        task_type = proposal.get("task_type", state.get("task_type", "general"))

        # Re-parse the conversation to extract IDs for the write call
        messages_text = " ".join(
            m.content for m in state["messages"] if hasattr(m, "content")
        )

        result = "❌ Could not determine the action to execute."

        if task_type == "assign_examiner":
            tool = tool_map.get("assign_examiner_to_slot")
            if tool:
                # Extract slot_id and examiner_id from messages (best-effort)
                import re
                slot_match = re.search(r"slot\s*[#:]?\s*(\d+)", messages_text, re.I)
                exam_match = re.search(r"examiner\s*[#:]?\s*(\d+)", messages_text, re.I)
                if slot_match and exam_match:
                    result = await tool.ainvoke(
                        {
                            "slot_id": int(slot_match.group(1)),
                            "examiner_id": int(exam_match.group(1)),
                            "confirm": True,
                        }
                    )
                else:
                    result = "❌ Không tìm thấy Slot ID hoặc Examiner ID trong cuộc hội thoại."

        elif task_type == "reschedule":
            tool = tool_map.get("reschedule_booking")
            if tool:
                import re
                booking_match = re.search(r"booking\s*[#:]?\s*(\d+)", messages_text, re.I)
                slot_match = re.search(r"slot\s*[#:]?\s*(\d+)", messages_text, re.I)
                if booking_match and slot_match:
                    result = await tool.ainvoke(
                        {
                            "booking_id": int(booking_match.group(1)),
                            "new_slot_id": int(slot_match.group(1)),
                            "confirm": True,
                        }
                    )
                else:
                    result = "❌ Không tìm thấy Booking ID hoặc Slot ID."

        return {
            "messages": [AIMessage(content=result)],
            "proposal": None,
            "confirmed": False,
        }

    return execute_node


# ── routing ───────────────────────────────────────────────────────────────────

def _route_after_propose(state: SchedulingState) -> str:
    """After propose_node: reads needing no confirm go straight to END."""
    if state.get("confirmed", False):
        return "__end__"
    return "confirm_node"


def _route_after_confirm(state: SchedulingState) -> str:
    """After confirm_node: if confirmed execute; else stay/end."""
    if state.get("confirmed", False):
        return "execute_node"
    return "__end__"


# ── factory ───────────────────────────────────────────────────────────────────

def create_scheduling_graph(tools: list, llm, checkpointer=None):
    """
    Build and compile the SchedulingGraph StateGraph.

    Args:
        tools: List of scheduling tools (from make_scheduling_tools + make_reschedule_tools).
        llm: LLM instance (from get_llm()).
        checkpointer: Optional LangGraph checkpointer for human-in-the-loop resume.
    """
    from langgraph.graph import END, START, StateGraph

    builder = StateGraph(SchedulingState)

    builder.add_node("classify_node", _make_classify_node(llm))
    builder.add_node("fetch_node", _make_fetch_node(tools))
    builder.add_node("propose_node", _make_propose_node(llm, tools))
    builder.add_node("confirm_node", confirm_node)
    builder.add_node("execute_node", _make_execute_node(tools))

    builder.add_edge(START, "classify_node")
    builder.add_edge("classify_node", "fetch_node")
    builder.add_edge("fetch_node", "propose_node")
    builder.add_conditional_edges("propose_node", _route_after_propose)
    builder.add_conditional_edges("confirm_node", _route_after_confirm)
    builder.add_edge("execute_node", END)

    return builder.compile(checkpointer=checkpointer)
