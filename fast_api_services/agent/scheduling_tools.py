"""
LangChain tool definitions for the scheduling agent (CENTER_ADMIN).

Tools operate via the SchedulingToolContext — they call FastAPI services
directly (async DB reads) and proxy writes to Django via HTTP.

All write tools use the same confirmation gate pattern as the booking tools:
    confirm=False → return warning string (agent relays to user)
    confirm=True  → execute Django call (only after user says "xác nhận")

Note: the actual confirmation gate for SchedulingGraph write operations is
enforced at the GRAPH level (confirm_node), but each tool retains its own
inline guard as defence-in-depth.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date as date_type
from typing import Any, Optional

import httpx
from sqlalchemy.ext.asyncio import async_sessionmaker

from fast_api_services.config import get_settings

logger = logging.getLogger(__name__)

_CONFIRM_REQUIRED = (
    "⚠️ Confirmation required. Please explicitly confirm (yes / xác nhận) "
    "before I proceed with this action."
)


@dataclass
class SchedulingToolContext:
    session_factory: async_sessionmaker
    user_token: str   # JWT — forwarded to Django for write calls
    center_id: int    # the admin's center (extracted from user profile)


def make_scheduling_tools(ctx: SchedulingToolContext) -> list:
    """Build CENTER_ADMIN scheduling tools bound to *ctx*."""
    from langchain_core.tools import tool  # lazy

    @tool
    async def list_examiners(
        available_date: Optional[str] = None,
        style: Optional[str] = None,
    ) -> str:
        """
        List examiners at the current admin's center.
        Args:
            available_date: Optional date filter (YYYY-MM-DD) — only returns
                examiners who are NOT on leave that day.
            style: Optional instrument style filter
                ("CLASSICAL_JAZZ", "ROCK_POP", "THEORY").
        Returns:
            Formatted list of examiners with daily capacity info.
        """
        from fast_api_services.services.examiner_service import (
            list_examiners as _list,
            get_examiner_daily_load,
        )

        parsed_date = date_type.fromisoformat(available_date) if available_date else None

        async with ctx.session_factory() as db:
            examiners = await _list(
                db,
                center_id=ctx.center_id,
                available_date=parsed_date,
                style=style,
            )
            lines = []
            for e in examiners:
                load = 0
                if parsed_date:
                    load = await get_examiner_daily_load(db, e.id, parsed_date)
                specs = ", ".join(e.specialization_names) or "—"
                lines.append(
                    f"[{e.id}] {e.name} | {specs} | "
                    f"Max/day: {e.max_exams_per_day} | Booked today: {load}"
                )

        if not lines:
            return "No available examiners found."
        return "\n".join(lines)

    @tool
    async def suggest_examiners_for_slot(slot_id: int) -> str:
        """
        Suggest suitable examiners for a specific exam slot, ranked by
        availability (least booked first).
        Args:
            slot_id: The exam slot ID.
        Returns:
            Ranked list of available examiners for that slot.
        """
        from fast_api_services.services.examiner_service import suggest_examiners_for_slot as _suggest

        async with ctx.session_factory() as db:
            suggestions = await _suggest(db, slot_id)

        if not suggestions:
            return f"No available examiners found for slot {slot_id}."

        lines = [
            f"[{s.examiner.id}] {s.examiner.name} — "
            f"exams today: {s.exams_today}/{s.examiner.max_exams_per_day}"
            for s in suggestions
        ]
        return "\n".join(lines)

    @tool
    async def get_exam_calendar(
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
    ) -> str:
        """
        View the exam calendar for the current admin's center.
        Shows all slots (including full ones) with their assigned examiners.
        Args:
            date_from: Optional start date (YYYY-MM-DD).
            date_to:   Optional end date (YYYY-MM-DD).
        Returns:
            Formatted exam calendar.
        """
        from fast_api_services.services.examiner_service import get_exam_calendar as _cal

        parsed_from = date_type.fromisoformat(date_from) if date_from else None
        parsed_to = date_type.fromisoformat(date_to) if date_to else None

        async with ctx.session_factory() as db:
            slots = await _cal(db, ctx.center_id, parsed_from, parsed_to)

        if not slots:
            return "No slots found in the requested date range."

        lines = []
        for s in slots:
            examiner_str = s.examiner_name or "⚠️ No examiner assigned"
            lines.append(
                f"[Slot {s.id}] {s.exam_date} {s.start_time} | {s.course_name} | "
                f"Booked: {s.capacity - s.available_capacity}/{s.capacity} | "
                f"Examiner: {examiner_str}"
            )
        return "\n".join(lines)

    @tool
    async def search_available_slots(
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        examiner_id: Optional[int] = None,
    ) -> str:
        """
        Search for available exam slots matching date and examiner criteria.
        Args:
            date_from: Optional earliest date (YYYY-MM-DD).
            date_to: Optional latest date (YYYY-MM-DD).
            examiner_id: Optional examiner ID filter.
        Returns:
            List of matching slots with IDs.
        """
        from fast_api_services.services.examiner_service import get_exam_calendar as _cal

        parsed_from = date_type.fromisoformat(date_from) if date_from else None
        parsed_to = date_type.fromisoformat(date_to) if date_to else None

        async with ctx.session_factory() as db:
            slots = await _cal(db, ctx.center_id, parsed_from, parsed_to)

        # Filter by examiner_id if provided
        if examiner_id is not None:
            slots = [s for s in slots if s.examiner_id == examiner_id]

        if not slots:
            return f"No slots found matching your criteria."

        lines = []
        for s in slots:
            examiner_str = s.examiner_name or "(no examiner assigned)"
            available = s.available_capacity if hasattr(s, 'available_capacity') else "?"
            lines.append(
                f"[Slot {s.id}] {s.exam_date} {s.start_time} | {s.course_name} | "
                f"Examiner: {examiner_str} | Seats: {available}"
            )
        return "\n".join(lines)

    @tool
    async def assign_examiner_to_slot(
        slot_id: int,
        examiner_id: int,
        confirm: bool = False,
    ) -> str:
        """
        Assign an examiner to an exam slot.
        IMPORTANT: Always show the examiner name, slot date/time, and ask the
        user to confirm BEFORE calling this tool with confirm=True.
        Args:
            slot_id: The exam slot ID.
            examiner_id: The examiner ID (from list_examiners or suggest_examiners_for_slot).
            confirm: Must be True after user confirms. Never set True without explicit consent.
        Returns:
            Success message or error details.
        """
        if not confirm:
            return (
                f"{_CONFIRM_REQUIRED}\n"
                f"Action: Assign examiner #{examiner_id} to slot #{slot_id}. "
                "Reply 'xác nhận' to proceed."
            )

        settings = get_settings()
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.post(
                    f"{settings.django_service_url}/api/centers/slots/{slot_id}/assign-examiner/",
                    json={"examiner_id": examiner_id},
                    headers={"Authorization": f"Bearer {ctx.user_token}"},
                )
            if resp.status_code == 200:
                data = resp.json()
                return (
                    f"✅ Examiner assigned. Slot {slot_id} — "
                    f"Examiner: {data.get('examiner_name', examiner_id)}"
                )
            return f"❌ Assignment failed (HTTP {resp.status_code}): {resp.text[:200]}"
        except Exception as exc:
            logger.error("assign_examiner_to_slot error: %s", exc)
            return f"❌ Error assigning examiner: {exc}"

    return [
        list_examiners,
        suggest_examiners_for_slot,
        search_available_slots,
        get_exam_calendar,
        assign_examiner_to_slot,
    ]


def make_reschedule_tools(ctx: SchedulingToolContext, user_id: int) -> list:
    """
    Reschedule tools usable by both CENTER_ADMIN and STUDENT/PARENT agents.
    Kept separate so BookingGraph can import only these two tools.
    """
    from langchain_core.tools import tool  # lazy

    @tool
    async def suggest_slots_for_reschedule(
        booking_id: int,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        city: Optional[str] = None,
    ) -> str:
        """
        Suggest alternative exam slots for an existing booking.
        Returns up to 10 available slots for the same course, in future dates.
        Args:
            booking_id: The booking ID to reschedule.
            date_from: Optional earliest date filter (YYYY-MM-DD).
            date_to:   Optional latest date filter (YYYY-MM-DD).
            city: Optional city filter.
        Returns:
            Formatted list of suggested slots.
        """
        from fast_api_services.services.catalog_service import suggest_slots_for_reschedule as _suggest

        async with ctx.session_factory() as db:
            slots = await _suggest(db, booking_id, user_id, date_from, date_to, city)

        if not slots:
            return f"No alternative slots found for booking {booking_id}."

        lines = [
            f"[Slot {s.id}] {s.center_name}, {s.center_city} — "
            f"{s.exam_date} {s.start_time} | {s.course_name} | "
            f"Seats left: {s.available_capacity}"
            for s in slots
        ]
        return "\n".join(lines)

    @tool
    async def reschedule_booking(
        booking_id: int,
        new_slot_id: int,
        reason: str = "",
        confirm: bool = False,
    ) -> str:
        """
        Reschedule a booking to a different exam slot.
        IMPORTANT: Always show the new slot details and ask the user to confirm
        BEFORE calling this tool with confirm=True.
        Args:
            booking_id: The booking to reschedule.
            new_slot_id: The new exam slot ID (from suggest_slots_for_reschedule).
            reason: Reason for rescheduling (optional).
            confirm: Must be True after user confirms. Never set True without consent.
        Returns:
            Success message or error details.
        """
        if not confirm:
            return (
                f"{_CONFIRM_REQUIRED}\n"
                f"Action: Reschedule booking #{booking_id} to slot #{new_slot_id}. "
                f"Reason: {reason or '—'}. Reply 'xác nhận' to proceed."
            )

        settings = get_settings()
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.post(
                    f"{settings.django_service_url}/api/bookings/{booking_id}/reschedule/",
                    json={"new_slot_id": new_slot_id, "reason": reason},
                    headers={"Authorization": f"Bearer {ctx.user_token}"},
                )
            if resp.status_code == 200:
                data = resp.json()
                return (
                    f"✅ Booking #{booking_id} rescheduled to slot {data.get('slot')}."
                )
            return f"❌ Reschedule failed (HTTP {resp.status_code}): {resp.text[:200]}"
        except Exception as exc:
            logger.error("reschedule_booking error: %s", exc)
            return f"❌ Error rescheduling booking: {exc}"

    return [suggest_slots_for_reschedule, reschedule_booking]
