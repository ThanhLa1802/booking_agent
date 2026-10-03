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

import asyncio
import logging
from dataclasses import dataclass
from datetime import date as date_type
from typing import Any, Optional

import httpx
from sqlalchemy.ext.asyncio import async_sessionmaker

from fast_api_services.agent.authorization import authorize_write
from fast_api_services.config import get_settings

logger = logging.getLogger(__name__)


def _get_redis_in_tool():
    """Thin wrapper so tests can patch fast_api_services.agent.scheduling_tools._get_redis_in_tool."""
    from fast_api_services.services.slot_cache import get_redis
    return get_redis()


_CONFIRM_REQUIRED = (
    "⚠️ Confirmation required. Please explicitly confirm (yes / xác nhận) "
    "before I proceed with this action."
)


@dataclass
class SchedulingToolContext:
    session_factory: async_sessionmaker
    user_token: str   # JWT — forwarded to Django for write calls
    center_id: int    # the admin's center (extracted from user profile)
    user_id: int = 0
    redis: Any = None
    # None = unmanaged (legacy/tests); router supplies a frozenset in production.
    authorized_actions: frozenset[str] | None = None


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
            get_examiner_daily_load,
        )
        from fast_api_services.services.examiner_service import (
            list_examiners as _list,
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
        from fast_api_services.services.examiner_service import (
            suggest_examiners_for_slot as _suggest,
        )

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
            return "Không có ca thi nào trong khoảng thời gian này."

        lines = [f"📅 **Lịch thi** — {len(slots)} ca thi"]
        current_date = None
        for s in slots:
            day = str(s.exam_date)
            if day != current_date:
                current_date = day
                lines.append(f"\n**{day}**")
                lines.append("| Giờ | Ca thi | Trung tâm | Đã đặt | Giám khảo |")
                lines.append("|-----|--------|-----------|--------|-----------|")
            booked = s.capacity - s.available_capacity
            examiner_str = s.examiner_name or "⚠️ Chưa phân công"
            lines.append(
                f"| {str(s.start_time)[:5]} | {s.course_name} | {s.center_name} "
                f"| {booked}/{s.capacity} | {examiner_str} |"
            )
        return "\n".join(lines)

    @tool
    async def get_examiner_schedule(
        examiner_id: int,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
    ) -> str:
        """
        View the exam schedule of ONE examiner (teacher), grouped by date.
        Use this when the admin asks for a specific teacher's schedule/calendar.
        Args:
            examiner_id: The examiner ID (from list_examiners).
            date_from: Optional start date (YYYY-MM-DD).
            date_to:   Optional end date (YYYY-MM-DD).
        Returns:
            The examiner's profile and their assigned slots as a table per date.
        """
        from fast_api_services.services.examiner_service import (
            get_examiner_schedule as _schedule,
        )

        parsed_from = date_type.fromisoformat(date_from) if date_from else None
        parsed_to = date_type.fromisoformat(date_to) if date_to else None

        async with ctx.session_factory() as db:
            result = await _schedule(db, examiner_id, parsed_from, parsed_to)

        if result is None:
            return f"❌ Không tìm thấy giám khảo ID {examiner_id}."

        examiner = result.examiner
        if ctx.center_id and examiner.center_id != ctx.center_id:
            return f"❌ Giám khảo ID {examiner_id} không thuộc trung tâm của bạn."

        specs = ", ".join(examiner.specialization_names) or "—"
        header = (
            f"👩‍🏫 **{examiner.name}** (ID {examiner.id})\n"
            f"Chuyên môn: {specs} · Tối đa {examiner.max_exams_per_day} ca/ngày"
        )

        slots = result.slots
        if not slots:
            return f"{header}\n\nKhông có ca thi nào trong khoảng thời gian này."

        lines = [header, f"\n📅 **Tổng: {len(slots)} ca thi**"]
        current_date = None
        for s in slots:
            day = str(s.exam_date)
            if day != current_date:
                current_date = day
                lines.append(f"\n**{day}**")
                lines.append("| Giờ | Ca thi | Trung tâm | Đã đặt |")
                lines.append("|-----|--------|-----------|--------|")
            booked = s.capacity - s.available_capacity
            lines.append(
                f"| {str(s.start_time)[:5]} | {s.course_name} | {s.center_name} "
                f"| {booked}/{s.capacity} |"
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
            return "No slots found matching your criteria."

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
        if not await authorize_write(
            ctx,
            "assign_examiner_to_slot",
            {"slot_id": slot_id, "examiner_id": examiner_id},
            confirm,
        ):
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

    @tool
    async def auto_plan_schedule(
        date_from: str,
        date_to: str,
    ) -> str:
        """
        Generate a batch exam schedule plan for a date range using OR-Tools.
        Fires a background task, waits for the plan (up to 15 s), and returns
        a formatted preview table for the admin to review and confirm.
        Args:
            date_from: Start date (YYYY-MM-DD).
            date_to:   End date (YYYY-MM-DD).
        Returns:
            Formatted plan preview with [TASK_ID:...] prefix.
        """
        import json as _json

        from fast_api_services.agent.scheduling_tools import _get_redis_in_tool

        settings = get_settings()

        # 1. Fire the Celery task via Django
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.post(
                    f"{settings.django_service_url}/api/centers/schedule/batch/",
                    json={"date_from": date_from, "date_to": date_to},
                    headers={"Authorization": f"Bearer {ctx.user_token}"},
                )
            if resp.status_code != 202:
                return (
                    f"❌ Không thể bắt đầu lập lịch "
                    f"(HTTP {resp.status_code}): {resp.text[:200]}"
                )
            task_id = resp.json().get("task_id")
            if not task_id:
                return "❌ Server không trả về task_id."
        except Exception as exc:
            return f"❌ Lỗi khi gọi server: {exc}"

        # 2. Poll Redis until plan ready (max 15 s)
        rc = _get_redis_in_tool()
        redis_key = f"schedule_task:{task_id}"
        plan_data = None
        for _ in range(15):
            await asyncio.sleep(1)
            raw = await rc.get(redis_key)
            if raw:
                parsed = _json.loads(raw)
                if parsed.get("status") != "PENDING":
                    plan_data = parsed
                    break

        if plan_data is None:
            return (
                f"[TASK_ID:{task_id}]\n"
                "⏳ Hệ thống vẫn đang tính toán lịch. "
                "Vui lòng gửi lại yêu cầu xếp lịch sau ít phút."
            )

        if plan_data.get("status") == "FAILURE":
            return (
                f"[TASK_ID:{task_id}]\n"
                f"❌ Lỗi khi lập lịch: {plan_data.get('error', 'Unknown error')}"
            )

        # 3. Format preview
        plan = plan_data.get("plan", [])
        unassigned = plan_data.get("unassigned", [])
        already_assigned = plan_data.get("already_assigned", 0)

        # Nothing to commit → never emit a TASK_ID (so the agent won't ask for
        # confirmation); just explain the state clearly.
        if not plan:
            if unassigned:
                lines = [
                    f"⚠️ **Không xếp được giám khảo cho {len(unassigned)} ca thi** "
                    f"trong {date_from} → {date_to}:"
                ]
                lines.append("| Ngày | Giờ | Môn thi | Lý do |")
                lines.append("|------|-----|---------|-------|")
                for item in unassigned:
                    lines.append(
                        f"| {item['exam_date']} | {item['start_time']} "
                        f"| {item['course_name']} | {item.get('reason', '—')} |"
                    )
                return "\n".join(lines)
            if already_assigned:
                return (
                    f"✅ Tất cả **{already_assigned} ca thi** trong "
                    f"{date_from} → {date_to} đã có giám khảo. Không cần xếp thêm."
                )
            return f"ℹ️ Không có ca thi nào cần xếp trong {date_from} → {date_to}."

        lines = [f"[TASK_ID:{task_id}]"]
        lines.append(f"📋 **Kế hoạch xếp lịch {date_from} → {date_to}**")
        lines.append(
            f"✅ Xếp được: **{len(plan)} slot** | "
            f"⚠️ Chưa xếp: **{len(unassigned)} slot**\n"
        )

        lines.append("| Ngày | Giờ | Môn thi | Giám khảo |")
        lines.append("|------|-----|---------|-----------|")
        for item in plan:
            lines.append(
                f"| {item['exam_date']} | {item['start_time']} "
                f"| {item['course_name']} | {item['examiner_name']} |"
            )

        if unassigned:
            lines.append("\n⚠️ **Slot chưa xếp được giám khảo:**")
            lines.append("| Ngày | Giờ | Môn thi | Lý do |")
            lines.append("|------|-----|---------|-------|")
            for item in unassigned:
                lines.append(
                    f"| {item['exam_date']} | {item['start_time']} "
                    f"| {item['course_name']} | {item.get('reason', '—')} |"
                )

        return "\n".join(lines)

    @tool
    async def confirm_schedule_plan(task_id: str, confirm: bool = False) -> str:
        """
        Commit a previously reviewed schedule plan to the database.
        Only call this after the admin has explicitly confirmed the plan.
        Args:
            task_id: The task_id returned by auto_plan_schedule.
            confirm: Must be True after user confirms. Never set True without consent.
        Returns:
            Success message or error details.
        """
        if not await authorize_write(
            ctx, "confirm_schedule_plan", {"task_id": task_id}, confirm
        ):
            return (
                f"{_CONFIRM_REQUIRED}\n"
                f"Action: Lưu kế hoạch xếp lịch (task {task_id}). "
                "Gõ 'xác nhận' để lưu vào hệ thống."
            )
        settings = get_settings()
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.post(
                    f"{settings.django_service_url}/api/centers/schedule/batch/{task_id}/confirm/",
                    headers={"Authorization": f"Bearer {ctx.user_token}"},
                )
            if resp.status_code == 200:
                data = resp.json()
                return (
                    f"✅ Đã lưu lịch thành công: "
                    f"**{data.get('assigned_count', 0)} giám khảo** được gán."
                )
            return f"❌ Lỗi lưu lịch (HTTP {resp.status_code}): {resp.text[:200]}"
        except Exception as exc:
            logger.error("confirm_schedule_plan error: %s", exc)
            return f"❌ Lỗi: {exc}"

    return [
        list_examiners,
        suggest_examiners_for_slot,
        search_available_slots,
        get_exam_calendar,
        get_examiner_schedule,
        assign_examiner_to_slot,
        auto_plan_schedule,
        confirm_schedule_plan,
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
        from fast_api_services.services.catalog_service import (
            suggest_slots_for_reschedule as _suggest,
        )

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
        if not await authorize_write(
            ctx,
            "reschedule_booking",
            {"booking_id": booking_id, "new_slot_id": new_slot_id, "reason": reason},
            confirm,
        ):
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
