"""
LangGraph state types for the Trinity multi-agent system.

BookingState   — used by BookingGraph (STUDENT / PARENT agent)
SchedulingState — used by SchedulingGraph (CENTER_ADMIN agent)

Both are TypedDicts so LangGraph can serialize/deserialize them via
the Redis checkpointer.
"""
from __future__ import annotations

from enum import Enum
from typing import Annotated, Optional

from langgraph.graph.message import add_messages
from typing_extensions import TypedDict


class TaskType(str, Enum):
    """Intent labels for the CENTER_ADMIN scheduling agent (structured output)."""

    ASSIGN_EXAMINER = "assign_examiner"
    VIEW_CALENDAR = "view_calendar"
    VIEW_EXAMINER_SCHEDULE = "view_examiner_schedule"
    LIST_EXAMINERS = "list_examiners"
    RESCHEDULE = "reschedule"
    BATCH_ASSIGN = "batch_assign"
    GENERAL = "general"


class BookingState(TypedDict):
    """State for the booking-focused agent (students and parents)."""

    messages: Annotated[list, add_messages]
    user_role: str          # "STUDENT" | "PARENT"


class ExaminerState(TypedDict):
    """State for the read-only reviewer agent (examiners)."""

    messages: Annotated[list, add_messages]
    user_role: str          # "EXAMINER"


class SchedulingState(TypedDict):
    """State for the scheduling-focused agent (center admins)."""

    messages: Annotated[list, add_messages]
    user_role: str          # "CENTER_ADMIN"
    # ── scheduling task context ──────────────────────────────────────────────
    task_type: str          # "assign_examiner" | "view_calendar" | "view_examiner_schedule" | "list_examiners" | "reschedule" | "batch_assign" | "general"
    proposal: Optional[dict]   # structured proposal waiting for human confirmation
    confirmed: bool            # True once the user has explicitly confirmed the proposal
    assignment_task_id: Optional[str]   # Celery task_id for batch schedule plans
