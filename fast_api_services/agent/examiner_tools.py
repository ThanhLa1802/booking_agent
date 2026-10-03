"""
LangChain tools for the EXAMINER agent.

Read-only: an examiner can ONLY view their own assigned exam slots. The examiner
is resolved server-side from the JWT (never from an LLM-supplied argument), so
the model can never widen its scope to another examiner.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date as date_type
from typing import Any, Optional

from sqlalchemy.ext.asyncio import async_sessionmaker

logger = logging.getLogger(__name__)

_LINKED_REQUIRED = (
    "❌ Tài khoản của bạn chưa được liên kết với hồ sơ giám khảo. "
    "Vui lòng liên hệ trung tâm để được hỗ trợ."
)


@dataclass
class ExaminerToolContext:
    session_factory: async_sessionmaker
    examiner_id: Optional[int] = None
    user_id: int = 0
    redis: Any = None


def make_examiner_tools(ctx: ExaminerToolContext) -> list:
    """Build read-only reviewer tools bound to *ctx*."""
    from langchain_core.tools import tool  # lazy to avoid torch crash

    @tool
    async def get_my_schedule(
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
    ) -> str:
        """
        View the logged-in examiner's OWN assigned exam slots, grouped by date.
        Use this whenever the examiner asks about their schedule, shifts, or
        which exams they are marking.
        Args:
            date_from: Optional start date (YYYY-MM-DD).
            date_to:   Optional end date (YYYY-MM-DD).
        Returns:
            The examiner's profile and their assigned slots as a table per date.
        """
        if ctx.examiner_id is None:
            return _LINKED_REQUIRED

        from fast_api_services.services.examiner_service import (
            get_examiner_schedule as _schedule,
        )

        parsed_from = date_type.fromisoformat(date_from) if date_from else None
        parsed_to = date_type.fromisoformat(date_to) if date_to else None

        async with ctx.session_factory() as db:
            result = await _schedule(db, ctx.examiner_id, parsed_from, parsed_to)

        if result is None:
            return "❌ Không tìm thấy hồ sơ giám khảo."

        examiner = result.examiner
        specs = ", ".join(examiner.specialization_names) or "—"
        header = (
            f"👩‍🏫 **{examiner.name}**\n"
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

    return [get_my_schedule]
