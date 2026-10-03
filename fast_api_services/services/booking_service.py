from typing import Optional

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from fast_api_services.schemas.models import BookingOut, SlotDetail

_COLUMNS = """
    b.id, b.slot_id, b.student_name, b.student_dob, b.status,
    b.notes, b.created_at,
    b.price, b.currency, b.payment_status, b.hold_expires_at,
    b.guardian_name, b.guardian_phone, b.contact_email,
    b.candidate_id_number, b.school, b.teacher_name, b.special_needs,
    b.reschedule_count,
    ec.name AS center_name, ec.city AS center_city,
    c.name AS course_name,
    s.exam_date, s.start_time
"""

_JOINS = """
    FROM bookings_booking b
    JOIN centers_examslot s ON s.id = b.slot_id
    JOIN centers_examcenter ec ON ec.id = s.center_id
    JOIN catalog_course c ON c.id = s.course_id
"""


def _row_to_booking(r) -> BookingOut:
    return BookingOut(
        id=r["id"],
        slot_id=r["slot_id"],
        slot_detail=SlotDetail(
            center=r["center_name"],
            city=r["center_city"],
            course=r["course_name"],
            exam_date=r["exam_date"],
            start_time=r["start_time"],
        ),
        student_name=r["student_name"],
        student_dob=r["student_dob"],
        status=r["status"],
        notes=r["notes"] or "",
        created_at=r["created_at"],
        price=r["price"],
        currency=r["currency"] or "VND",
        payment_status=r["payment_status"],
        hold_expires_at=r["hold_expires_at"],
        guardian_name=r["guardian_name"] or "",
        guardian_phone=r["guardian_phone"] or "",
        contact_email=r["contact_email"] or "",
        candidate_id_number=r["candidate_id_number"] or "",
        school=r["school"] or "",
        teacher_name=r["teacher_name"] or "",
        special_needs=r["special_needs"] or "",
        reschedule_count=r["reschedule_count"] or 0,
    )


async def list_user_bookings(db: AsyncSession, user_id: int) -> list[BookingOut]:
    query = f"""
        SELECT {_COLUMNS}
        {_JOINS}
        WHERE b.user_id = :user_id
        ORDER BY b.created_at DESC
    """
    rows = (await db.execute(text(query), {"user_id": user_id})).mappings().all()
    return [_row_to_booking(r) for r in rows]


async def get_booking(
    db: AsyncSession, booking_id: int, user_id: int
) -> Optional[BookingOut]:
    query = f"""
        SELECT {_COLUMNS}
        {_JOINS}
        WHERE b.id = :booking_id AND b.user_id = :user_id
    """
    row = (
        await db.execute(text(query), {"booking_id": booking_id, "user_id": user_id})
    ).mappings().first()
    if not row:
        return None
    return _row_to_booking(row)
