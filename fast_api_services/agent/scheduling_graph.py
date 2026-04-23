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

import calendar as _calendar
import json
import logging
import re as _re
from datetime import date as _date
from typing import Any

import httpx
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from fast_api_services.config import get_settings

from .state import SchedulingState

logger = logging.getLogger(__name__)


def _extract_date_range(text: str):
    """Extract (date_from, date_to) strings from Vietnamese natural language."""
    today = _date.today()
    year = today.year
    m = _re.search(r"tháng\s*(\d{1,2})(?:\s*(?:năm\s*)?(\d{4}))?", text, _re.I)
    if m:
        month = int(m.group(1))
        y = int(m.group(2)) if m.group(2) else year
        if 1 <= month <= 12:
            last = _calendar.monthrange(y, month)[1]
            return f"{y:04d}-{month:02d}-01", f"{y:04d}-{month:02d}-{last:02d}"
    r = _re.search(r"(\d{4}-\d{2}-\d{2})\s*(?:đến|to|-)\s*(\d{4}-\d{2}-\d{2})", text)
    if r:
        return r.group(1), r.group(2)
    return None, None


def _extract_examiner_id(text: str) -> int | None:
    """Extract examiner ID from Vietnamese text like 'giám khảo ID 2' or 'examiner 2'."""
    patterns = [
        r"(?:giám\s*khảo|examiner|gk)\s+(?:ID\s*)?(\d+)",
        r"ID\s*(\d+)\s*(?:giám\s*khảo|examiner)",
    ]
    for pattern in patterns:
        m = _re.search(pattern, text, _re.I)
        if m:
            return int(m.group(1))
    return None


def _extract_slot_id(text: str) -> int | None:
    """Extract slot ID from text like 'slot 70' or 'slot ID 70'."""
    m = _re.search(r"(?:slot|khe)\s+(?:ID\s*)?(\d+)", text, _re.I)
    if m:
        return int(m.group(1))
    return None


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
            return {"task_type": "general"}

        # Skip classification if already confirmed with a proposal (resume from prev turn)
        if state.get("proposal") and state.get("confirmed"):
            return {"task_type": state.get("task_type", "general")}

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
        # Preserve proposal/confirmed from previous turn if they exist
        return {
            "task_type": task_type,
            "proposal": state.get("proposal"),  # preserve if already set
            "confirmed": state.get("confirmed", False),  # preserve if already set
        }

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

        # Extract identifiers from user message
        date_from, date_to = _extract_date_range(user_msg)
        examiner_id = _extract_examiner_id(user_msg)
        slot_id = _extract_slot_id(user_msg)

        if task_type == "view_calendar":
            # Show calendar for requested date range
            tool = tool_map.get("get_exam_calendar")
            if tool:
                cal_args: dict = {}
                if date_from:
                    cal_args["date_from"] = date_from
                if date_to:
                    cal_args["date_to"] = date_to
                fetched_text = await tool.ainvoke(cal_args)

        elif task_type == "assign_examiner":
            # Search slots by date + examiner if both provided
            if date_from and examiner_id is not None:
                tool = tool_map.get("search_available_slots")
                if tool:
                    search_args = {"date_from": date_from}
                    if date_to:
                        search_args["date_to"] = date_to
                    search_args["examiner_id"] = examiner_id
                    fetched_text = await tool.ainvoke(search_args)
                    if fetched_text and "No slots found" not in fetched_text:
                        # Found slots, extract first slot ID for proposal
                        pass
            else:
                # Fall back to calendar view
                tool = tool_map.get("get_exam_calendar")
                if tool:
                    cal_args: dict = {}
                    if date_from:
                        cal_args["date_from"] = date_from
                    if date_to:
                        cal_args["date_to"] = date_to
                    fetched_text = await tool.ainvoke(cal_args)
                    
                if examiner_id is None and date_from is None:
                    fetched_text = (
                        "❌ Vui lòng cung cấp: ngày tháng và ID giám khảo. "
                        "Ví dụ: 'Đặt giám khảo ID 2 ngày 10 tháng 5 năm 2026'"
                    )

        elif task_type == "reschedule":
            # For reschedule we just summarise — let propose_node do the heavy lifting
            fetched_text = f"Received reschedule request: {user_msg}"

        if fetched_text:
            return {
                "messages": [AIMessage(content=f"[FETCH] {fetched_text}")],
                "proposal": state.get("proposal"),  # preserve from previous turn
                "confirmed": state.get("confirmed", False),  # preserve from previous turn
            }
        return {
            "task_type": task_type,
            "proposal": state.get("proposal"),  # preserve from previous turn
            "confirmed": state.get("confirmed", False),  # preserve from previous turn
        }

    return fetch_node


# ── node: propose ─────────────────────────────────────────────────────────────

def _make_propose_node(llm, tools: list):
    """Generate a clear natural-language proposal for the admin to confirm."""
    tool_map = {t.name: t for t in tools}

    async def propose_node(state: SchedulingState) -> dict:
        task_type = state.get("task_type", "general")

        # For view_calendar and general, no confirmation needed — just reply directly
        if task_type in ("view_calendar", "general"):
            system = SystemMessage(
                content=(
                    "Bạn là trợ lý xếp lịch thi cho quản trị viên trung tâm. "
                    "Dựa vào dữ liệu đã lấy từ hệ thống (dòng bắt đầu bằng [FETCH]), "
                    "hãy trả lời bằng tiếng Việt một cách rõ ràng và đầy đủ. "
                    "Nếu không có dữ liệu [FETCH], hãy thông báo không tìm thấy slot nào "
                    "trong khoảng thời gian yêu cầu."
                )
            )
            response = await llm.ainvoke([system] + state["messages"])
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
        user_msg = last_human.content if last_human else ""
        
        # Extract IDs from the full conversation
        all_text = " ".join([m.content for m in state["messages"] if hasattr(m, "content")])
        examiner_id = _extract_examiner_id(all_text)
        slot_id = _extract_slot_id(all_text)
        date_from, date_to = _extract_date_range(all_text)
        
        system = SystemMessage(
            content=(
                "You are a scheduling assistant. Based on the conversation and fetched data, "
                "create a clear, concise action proposal in Vietnamese that the admin needs to confirm.\n"
                "If you see fetched data (starting with [FETCH]), use it to fill in specific slot or examiner details.\n"
                "Format:\n"
                "🗓️ **Đề xuất hành động:**\n"
                "<detail>\n\n"
                "Reply 'xác nhận' to proceed or 'hủy' to cancel."
            )
        )
        response = await llm.ainvoke([system] + state["messages"])
        proposal_text = response.content

        # Store structured proposal for execute_node — preserve conversation for ID extraction
        proposal = {
            "task_type": task_type,
            "description": proposal_text,
            "conversation_messages": [
                m.content for m in state["messages"] if hasattr(m, "content")
            ],
            "examiner_id": examiner_id,  # extracted from conversation
            "slot_id": slot_id,
            "date_from": date_from,
            "date_to": date_to,
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

        result = "❌ Could not determine the action to execute."

        if task_type == "assign_examiner":
            tool = tool_map.get("assign_examiner_to_slot")
            if tool:
                # Use extracted IDs from proposal or try to extract from conversation
                slot_id = proposal.get("slot_id")
                examiner_id = proposal.get("examiner_id")
                
                # Fallback: extract from conversation messages if not in proposal
                if not slot_id or not examiner_id:
                    proposal_messages = proposal.get("conversation_messages", [])
                    messages_text = " ".join(proposal_messages) if proposal_messages else ""
                    
                    if not slot_id:
                        m = _re.search(r"slot\s*[#:]?\s*(\d+)", messages_text, _re.I)
                        if m:
                            slot_id = int(m.group(1))
                    
                    if not examiner_id:
                        m = _re.search(r"(?:giám\s*khảo|examiner)\s*[#:]?\s*(\d+)", messages_text, _re.I)
                        if m:
                            examiner_id = int(m.group(1))
                
                if slot_id and examiner_id:
                    result = await tool.ainvoke(
                        {
                            "slot_id": slot_id,
                            "examiner_id": examiner_id,
                            "confirm": True,
                        }
                    )
                else:
                    result = (
                        f"❌ Không tìm thấy Slot ID hoặc Examiner ID. "
                        f"Có slot_id={slot_id}, examiner_id={examiner_id}."
                    )

        elif task_type == "reschedule":
            tool = tool_map.get("reschedule_booking")
            if tool:
                # Extract from proposal or conversation
                proposal_messages = proposal.get("conversation_messages", [])
                messages_text = " ".join(proposal_messages) if proposal_messages else ""
                
                booking_match = _re.search(r"booking\s*[#:]?\s*(\d+)", messages_text, _re.I)
                slot_match = _re.search(r"slot\s*[#:]?\s*(\d+)", messages_text, _re.I)
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

def _route_from_start(state: SchedulingState) -> str:
    """If a confirmed proposal was injected from a previous turn, skip straight to execute."""
    if state.get("proposal") and state.get("confirmed"):
        return "execute_node"
    return "classify_node"


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

    builder.add_conditional_edges(START, _route_from_start, {"classify_node": "classify_node", "execute_node": "execute_node"})
    builder.add_edge("classify_node", "fetch_node")
    builder.add_edge("fetch_node", "propose_node")
    builder.add_conditional_edges("propose_node", _route_after_propose)
    builder.add_conditional_edges("confirm_node", _route_after_confirm)
    builder.add_edge("execute_node", END)

    return builder.compile(checkpointer=checkpointer)
