"""
SchedulingGraph — LangGraph StateGraph for CENTER_ADMIN exam scheduling.

Graph topology:
    START ──(resume? proposal+confirmed)──────────────→ execute_node → END
          │
          └─→ classify_node → fetch_node → propose_node → END

    * propose_node always ends the turn. For write ops it sets
      proposal + confirmed=False; the agent router persists that proposal
      (Redis) and, on the next turn, injects it with confirmed=True so
      START routes straight to execute_node. Read ops (view_calendar /
      general) set confirmed=True and end immediately.

batch_assign flow:
    fetch_node calls auto_plan_schedule (fires Celery + polls Redis)
    propose_node shows plan preview table → admin confirms in a later turn
    execute_node calls confirm_schedule_plan (writes to DB)
"""
from __future__ import annotations

import calendar as _calendar
import logging
import re as _re
from datetime import date as _date
from datetime import timedelta as _timedelta

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from .state import SchedulingState

logger = logging.getLogger(__name__)


def _extract_date_range(text: str):
    """Extract (date_from, date_to) strings from Vietnamese natural language."""
    today = _date.today()
    year = today.year
    lower = text.lower()

    # Relative weeks: "tuần này" (current), "tuần sau/tới" (next), "tuần trước/rồi" (last)
    if "tuần" in lower or "tuan" in lower:
        monday = today - _timedelta(days=today.weekday())
        if "sau" in lower or "tới" in lower or "toi" in lower:
            monday += _timedelta(days=7)
        elif "trước" in lower or "truoc" in lower or "rồi" in lower:
            monday -= _timedelta(days=7)
        sunday = monday + _timedelta(days=6)
        return monday.isoformat(), sunday.isoformat()

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
    """Extract examiner ID from Vietnamese text like 'giám khảo ID 2' or 'giáo viên 2'."""
    patterns = [
        r"(?:giám\s*khảo|giáo\s*viên|giao\s*vien|examiner|teacher|gk|gv)\s+(?:ID\s*)?(\d+)",
        r"ID\s*(\d+)\s*(?:giám\s*khảo|giáo\s*viên|giao\s*vien|examiner|teacher)",
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


def _default_range_forward() -> tuple[str, str]:
    """Default read window when the admin gives no date: today → +60 days."""
    today = _date.today()
    return today.isoformat(), (today + _timedelta(days=60)).isoformat()


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
                "  assign_examiner       — assigning or changing which examiner covers a single slot\n"
                "  view_calendar         — viewing the exam schedule or calendar of the center\n"
                "  view_examiner_schedule — viewing the schedule/exams of a SPECIFIC examiner "
                "(keywords: giáo viên, giám khảo, examiner, teacher, 'lịch của ...')\n"
                "  reschedule            — rescheduling a student\'s booking to a new slot\n"
                "  batch_assign          — auto-schedule / assign examiners for a full week or month\n"
                "  general               — anything else (questions, greetings, etc.)\n\n"
                "Respond with ONLY the task_type string, nothing else."
            )
        )
        response = await llm.ainvoke([classification_prompt, last_human])
        task_type = response.content.strip().lower()
        if task_type not in (
            "assign_examiner",
            "view_calendar",
            "view_examiner_schedule",
            "reschedule",
            "batch_assign",
            "general",
        ):
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
        user_msg = str(last_human.content) if last_human else ""
        task_type = state.get("task_type", "general")
        fetched_text = ""

        # Extract identifiers from user message
        date_from, date_to = _extract_date_range(user_msg)
        examiner_id = _extract_examiner_id(user_msg)
        slot_id = _extract_slot_id(user_msg)

        if task_type == "view_calendar":
            # Show calendar for requested date range (default: upcoming 60 days)
            tool = tool_map.get("get_exam_calendar")
            if tool:
                if not date_from and not date_to:
                    date_from, date_to = _default_range_forward()
                cal_args: dict = {}
                if date_from:
                    cal_args["date_from"] = date_from
                if date_to:
                    cal_args["date_to"] = date_to
                fetched_text = await tool.ainvoke(cal_args)

        elif task_type == "view_examiner_schedule":
            # A specific examiner's schedule. Without an ID, list examiners to pick from.
            if examiner_id is None:
                tool = tool_map.get("list_examiners")
                if tool:
                    listing = await tool.ainvoke({})
                    fetched_text = (
                        "Bạn muốn xem lịch của giám khảo nào? "
                        "Vui lòng cho ID:\n" + listing
                    )
            else:
                tool = tool_map.get("get_examiner_schedule")
                if tool:
                    if not date_from and not date_to:
                        date_from, date_to = _default_range_forward()
                    sched_args: dict = {"examiner_id": examiner_id}
                    if date_from:
                        sched_args["date_from"] = date_from
                    if date_to:
                        sched_args["date_to"] = date_to
                    fetched_text = await tool.ainvoke(sched_args)

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
                    fallback_args: dict = {}
                    if date_from:
                        fallback_args["date_from"] = date_from
                    if date_to:
                        fallback_args["date_to"] = date_to
                    fetched_text = await tool.ainvoke(fallback_args)

                if examiner_id is None and date_from is None:
                    fetched_text = (
                        "❌ Vui lòng cung cấp: ngày tháng và ID giám khảo. "
                        "Ví dụ: 'Đặt giám khảo ID 2 ngày 10 tháng 5 năm 2026'"
                    )

        elif task_type == "reschedule":
            # For reschedule we just summarise — let propose_node do the heavy lifting
            fetched_text = f"Received reschedule request: {user_msg}"

        elif task_type == "batch_assign":
            tool = tool_map.get("auto_plan_schedule")
            if tool:
                plan_args: dict = {}
                if date_from:
                    plan_args["date_from"] = date_from
                if date_to:
                    plan_args["date_to"] = date_to
                if not plan_args.get("date_from"):
                    fetched_text = (
                        "❌ Vui lòng cho biết khoảng thời gian. "
                        "Ví dụ: 'Xếp lịch giám khảo tháng 6 năm 2026'"
                    )
                else:
                    fetched_text = await tool.ainvoke(plan_args)
            else:
                fetched_text = "❌ Tool auto_plan_schedule not available."

            # Extract task_id from the [TASK_ID:...] prefix
            task_id_match = _re.search(r"\[TASK_ID:([^\]]+)\]", fetched_text)
            assignment_task_id = task_id_match.group(1) if task_id_match else None

            return {
                "messages": [AIMessage(content=f"[FETCH] {fetched_text}")],
                "proposal": state.get("proposal"),
                "confirmed": state.get("confirmed", False),
                "assignment_task_id": assignment_task_id,
            }

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

        # For read-only views: present fetched data verbatim; use LLM only for fallback/general
        if task_type in ("view_calendar", "view_examiner_schedule", "general"):
            # Extract [FETCH] content directly — avoid LLM reformatting real data
            fetch_messages = [
                m for m in state["messages"]
                if hasattr(m, "content") and str(m.content).startswith("[FETCH]")
            ]
            if fetch_messages:
                plan_text = fetch_messages[-1].content.removeprefix("[FETCH] ").strip()
                return {
                    "messages": [AIMessage(content=plan_text)],
                    "proposal": None,
                    "confirmed": True,
                }
            # No real data — ask LLM for a graceful fallback message only
            system = SystemMessage(
                content=(
                    "Bạn là trợ lý xếp lịch thi cho quản trị viên trung tâm âm nhạc Trinity. "
                    "Không tìm thấy dữ liệu từ hệ thống. "
                    "Hãy thông báo ngắn gọn bằng tiếng Việt rằng không có dữ liệu trong khoảng thời gian yêu cầu."
                )
            )
            response = await llm.ainvoke([system] + state["messages"])
            return {
                "messages": [AIMessage(content=response.content)],
                "proposal": None,
                "confirmed": True,
            }

        # For write operations, build a structured proposal
        last_human = next(
            (m for m in reversed(state["messages"]) if isinstance(m, HumanMessage)),
            None,
        )
        user_msg = last_human.content if last_human else ""

        # batch_assign: plan preview is already in [FETCH] — present it verbatim.
        # NEVER re-process through LLM: it will hallucinate fake subjects/dates.
        if task_type == "batch_assign":
            task_id = state.get("assignment_task_id")

            # Extract the [FETCH] message content (already formatted by auto_plan_schedule)
            fetch_messages = [
                m for m in state["messages"]
                if hasattr(m, "content") and str(m.content).startswith("[FETCH]")
            ]
            fetch_text = fetch_messages[-1].content if fetch_messages else ""
            # Strip the [FETCH] prefix — the rest is the formatted plan or error
            plan_text = fetch_text.removeprefix("[FETCH] ").strip()

            has_error = "❌" in plan_text or not task_id

            if has_error:
                # Present the error directly — no LLM, no confirmation prompt
                error_display = plan_text if plan_text else "❌ Không thể bắt đầu lập lịch. Vui lòng thử lại."
                return {
                    "messages": [AIMessage(content=error_display)],
                    "proposal": None,
                    "confirmed": True,  # no confirmation needed for errors
                }

            # ⏳ case: task dispatched but OR-Tools not done within 15s poll
            if "⏳" in plan_text:
                return {
                    "messages": [AIMessage(content=plan_text)],
                    "proposal": None,
                    "confirmed": True,  # no confirmation — task still computing
                }

            # Success: append confirmation prompt directly to the tool's output
            display = plan_text + "\n\nGõ **xác nhận** để lưu lịch vào hệ thống, hoặc **hủy** để bỏ qua."
            proposal = {
                "task_type": "batch_assign",
                "description": display,
                "task_id": task_id,
            }
            return {
                "messages": [AIMessage(content=display)],
                "proposal": proposal,
                "confirmed": False,
            }

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

        elif task_type == "batch_assign":
            tool = tool_map.get("confirm_schedule_plan")
            task_id = proposal.get("task_id")
            if tool and task_id:
                result = await tool.ainvoke({"task_id": task_id})
            elif not task_id:
                result = "❌ Không tìm thấy task_id trong proposal."
            else:
                result = "❌ Tool confirm_schedule_plan không khả dụng."

        return {
            "messages": [AIMessage(content=result)],
            "proposal": None,
            "confirmed": False,
            "assignment_task_id": None,
        }

    return execute_node


# ── routing ───────────────────────────────────────────────────────────────────

def _route_from_start(state: SchedulingState) -> str:
    """If a confirmed proposal was injected from a previous turn, skip straight to execute."""
    if state.get("proposal") and state.get("confirmed"):
        return "execute_node"
    return "classify_node"


def _route_after_propose(state: SchedulingState) -> str:
    """Always end the turn after propose_node.

    - Read ops (view_calendar, general): propose_node already sets confirmed=True.
    - Write ops: end the turn so the admin can review the proposal.
      The NEXT turn is handled by the agent router's _resume mechanism,
      which injects the stored proposal and routes directly to execute_node.
    """
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
    builder.add_node("execute_node", _make_execute_node(tools))

    builder.add_conditional_edges(START, _route_from_start, {"classify_node": "classify_node", "execute_node": "execute_node"})
    builder.add_edge("classify_node", "fetch_node")
    builder.add_edge("fetch_node", "propose_node")
    builder.add_conditional_edges("propose_node", _route_after_propose)
    builder.add_edge("execute_node", END)

    return builder.compile(checkpointer=checkpointer)
