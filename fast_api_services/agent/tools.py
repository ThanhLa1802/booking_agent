"""
LangChain tool definitions for the Trinity exam booking agent.

All tools are pure functions (no side effects on their own) except create_booking
and cancel_booking which require explicit confirm=True — the agent MUST ask the
user for confirmation before setting confirm=True on any write tool.

Usage:
    tools = make_tools(ctx)   # ctx contains db, redis, user_id, embeddings, ...
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Optional

import httpx
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from fast_api_services.config import get_settings
from fast_api_services.services.booking_service import get_booking, list_user_bookings
from fast_api_services.services.catalog_service import list_available_slots, list_courses
from fast_api_services.services.slot_cache import get_slot_availability

from .rag import search_docs as _search_docs

logger = logging.getLogger(__name__)

_CONFIRM_REQUIRED = (
    "⚠️ Confirmation required. Please explicitly confirm (yes / xác nhận) "
    "before I proceed with this action."
)


@dataclass
class ToolContext:
    session_factory: async_sessionmaker  # each tool opens its own session
    redis: Any  # aioredis client
    user_id: int
    embeddings: Any  # Embeddings (lazy type to avoid heavy import)
    persist_dir: str


def make_tools(ctx: ToolContext) -> list:  # list[BaseTool]
    """
    Build and return the 7 agent tools, each bound to the request context.
    Tools are defined as closures so they capture ctx without globals.
    """
    from langchain_core.tools import tool  # lazy to avoid torch crash

    @tool
    async def search_exam_docs(query: str, doc_type: Optional[str] = None) -> str:
        """
        Search Trinity exam documentation (syllabus, policies, FAQ).
        Args:
            query: What to search for.
            doc_type: Optional filter — "syllabus", "policy", or "faq".
        Returns:
            Concatenated relevant text chunks.
        """
        results = _search_docs(query, ctx.embeddings, ctx.persist_dir, doc_type)
        if not results:
            return "No relevant documents found."
        return "\n\n---\n\n".join(results)

    @tool
    async def list_courses(
        style: Optional[str] = None,
        grade: Optional[int] = None,
    ) -> str:
        """
        List available exam courses.
        Args:
            style: Optional — "CLASSICAL_JAZZ", "ROCK_POP", or "THEORY".
            grade: Optional — exam grade 1-8.
        Returns:
            Formatted list of courses with fees.
        """
        from fast_api_services.services.catalog_service import list_courses as _list

        async with ctx.session_factory() as db:
            courses = await _list(db, style=style, grade=grade)
        if not courses:
            return "No courses found."
        lines = [
            f"[{c.id}] {c.instrument_name} — {c.style_display} Grade {c.grade} | {c.name} | "
            f"{c.duration_minutes} min | Fee: {c.fee} VND"
            for c in courses
        ]
        return "\n".join(lines)

    @tool
    async def list_available_slots(
        course_id: int,
        city: Optional[str] = None,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
    ) -> str:
        """
        List available exam slots for a course.
        Args:
            course_id: The course ID (from list_courses).
            city: Optional city filter (e.g. "Hanoi", "Ho Chi Minh City").
            date_from: Optional start date filter (YYYY-MM-DD).
            date_to: Optional end date filter (YYYY-MM-DD).
        Returns:
            Formatted slot list with availability counts.
        """
        async with ctx.session_factory() as db:
            slots = await _list_slots(db, course_id, city, date_from, date_to)
        if not slots:
            return "No available slots found."
        lines = []
        for s in slots:
            avail = await get_slot_availability(ctx.redis, s.id)
            remaining = avail if avail is not None else "?"
            lines.append(
                f"[Slot {s.id}] {s.center_name}, {s.center_city} — "
                f"{s.exam_date} {s.start_time} | {s.course_name} | "
                f"Seats left: {remaining}"
            )
        return "\n".join(lines)

    @tool
    async def get_booking_detail(booking_id: int) -> str:
        """
        Get details of a specific booking belonging to the current user.
        Args:
            booking_id: The booking ID.
        Returns:
            Booking details or error message.
        """
        async with ctx.session_factory() as db:
            booking = await get_booking(db, booking_id, ctx.user_id)
        if booking is None:
            return f"Booking {booking_id} not found."
        d = booking.slot_detail
        return (
            f"Booking #{booking.id}: {booking.student_name} (DOB: {booking.student_dob})\n"
            f"Status: {booking.status}\n"
            f"Slot: {d.course}, {d.center}, {d.city} — {d.exam_date} {d.start_time}\n"
            f"Notes: {booking.notes or 'None'}"
        )

    @tool
    async def list_my_bookings() -> str:
        """
        List all bookings for the current logged-in user.
        Returns:
            Summary of all bookings.
        """
        async with ctx.session_factory() as db:
            bookings = await list_user_bookings(db, ctx.user_id)
        if not bookings:
            return "You have no bookings yet."
        lines = [
            f"#{b.id} — {b.student_name} | {b.slot_detail.course} | "
            f"{b.slot_detail.exam_date} | Status: {b.status}"
            for b in bookings
        ]
        return "\n".join(lines)

    @tool
    async def create_booking(
        slot_id: int,
        student_name: str,
        student_dob: str,
        notes: str = "",
        confirm: bool = False,
    ) -> str:
        """
        Create an exam booking for the current user.
        IMPORTANT: Always summarise the details and ask the user to confirm BEFORE
        calling this tool with confirm=True.
        Args:
            slot_id: The exam slot ID.
            student_name: Full name of the student.
            student_dob: Date of birth (YYYY-MM-DD).
            notes: Optional notes.
            confirm: Must be True (user confirmed). Never set True without user consent.
        Returns:
            Booking confirmation or error message.
        """
        if not confirm:
            return (
                f"{_CONFIRM_REQUIRED}\n"
                f"Action: Create booking — Slot {slot_id}, Student: {student_name} "
                f"(DOB: {student_dob}). Reply 'xác nhận' to proceed."
            )
        settings = get_settings()
        payload = {
            "slot_id": slot_id,
            "student_name": student_name,
            "student_dob": student_dob,
            "notes": notes,
            "confirm": True,
        }
        headers: dict[str, str] = {}  # auth handled by Django via shared secret or user token
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.post(
                    f"{settings.django_service_url}/api/bookings/",
                    json=payload,
                    headers={"X-User-Id": str(ctx.user_id), **headers},
                )
            if resp.status_code == 201:
                data = resp.json()
                return f"✅ Booking created! ID: {data.get('id')} — {student_name}"
            return f"❌ Booking failed (HTTP {resp.status_code}): {resp.text[:200]}"
        except Exception as exc:
            logger.error("create_booking error: %s", exc)
            return f"❌ Error creating booking: {exc}"

    @tool
    async def cancel_booking(
        booking_id: int,
        reason: str = "",
        confirm: bool = False,
    ) -> str:
        """
        Cancel an existing booking.
        IMPORTANT: Always confirm with the user BEFORE calling this with confirm=True.
        Args:
            booking_id: The booking ID to cancel.
            reason: Reason for cancellation (optional).
            confirm: Must be True (user confirmed). Never set True without user consent.
        Returns:
            Cancellation result or error.
        """
        if not confirm:
            return (
                f"{_CONFIRM_REQUIRED}\n"
                f"Action: Cancel Booking #{booking_id}. Reply 'xác nhận' to confirm."
            )
        settings = get_settings()
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.post(
                    f"{settings.django_service_url}/api/bookings/{booking_id}/cancel/",
                    json={"reason": reason, "confirm": True},
                    headers={"X-User-Id": str(ctx.user_id)},
                )
            if resp.status_code == 200:
                return f"✅ Booking #{booking_id} cancelled."
            return f"❌ Cancel failed (HTTP {resp.status_code}): {resp.text[:200]}"
        except Exception as exc:
            logger.error("cancel_booking error: %s", exc)
            return f"❌ Error cancelling booking: {exc}"

    return [
        search_exam_docs,
        list_courses,
        list_available_slots,
        get_booking_detail,
        list_my_bookings,
        create_booking,
        cancel_booking,
    ]


# ── private helpers ───────────────────────────────────────────────────────────

async def _list_slots(
    db: AsyncSession,
    course_id: int,
    city: Optional[str],
    date_from: Optional[str],
    date_to: Optional[str],
):
    """Thin wrapper calling the catalog service with optional date/city filters."""
    from fast_api_services.services.catalog_service import list_available_slots as _svc
    return await _svc(db, course_id=course_id, city=city, date_from=date_from, date_to=date_to)
