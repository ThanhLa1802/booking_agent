"""
LangGraph state types for the Trinity multi-agent system.

BookingState   — used by BookingGraph (STUDENT / PARENT agent)
SchedulingState — used by SchedulingGraph (CENTER_ADMIN agent)

Both are TypedDicts so LangGraph can serialize/deserialize them via
the Redis checkpointer.
"""
from __future__ import annotations

from typing import Annotated, Optional

from langgraph.graph.message import add_messages
from typing_extensions import TypedDict


class BookingState(TypedDict):
    """State for the booking-focused agent (students and parents)."""

    messages: Annotated[list, add_messages]
    user_role: str          # "STUDENT" | "PARENT"


class SchedulingState(TypedDict):
    """State for the scheduling-focused agent (center admins)."""

    messages: Annotated[list, add_messages]
    user_role: str          # "CENTER_ADMIN"
    # ── scheduling task context ──────────────────────────────────────────────
    task_type: str          # "assign_examiner" | "view_calendar" | "reschedule" | "general"
    proposal: Optional[dict]   # structured proposal waiting for human confirmation
    confirmed: bool            # True once the user has explicitly confirmed the proposal
