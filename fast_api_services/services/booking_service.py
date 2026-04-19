from typing import Optional
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from fast_api_services.schemas.models import BookingOut, SlotDetail


async def list_user_bookings(db: AsyncSession, user_id: int) -> list[BookingOut]:
    query = """
        SELECT b.id, b.slot_id, b.student_name, b.student_dob, b.status,
               b.notes, b.created_at,
               ec.name AS center_name, ec.city AS center_city,
               c.name AS course_name,
               s.exam_date, s.start_time
        FROM bookings_booking b
        JOIN centers_examslot s ON s.id = b.slot_id
        JOIN centers_examcenter ec ON ec.id = s.center_id
        JOIN catalog_course c ON c.id = s.course_id
        WHERE b.user_id = :user_id
        ORDER BY b.created_at DESC
    """
    rows = (await db.execute(text(query), {"user_id": user_id})).mappings().all()
    return [
        BookingOut(
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
        )
        for r in rows
    ]


async def get_booking(
    db: AsyncSession, booking_id: int, user_id: int
) -> Optional[BookingOut]:
    query = """
        SELECT b.id, b.slot_id, b.student_name, b.student_dob, b.status,
               b.notes, b.created_at,
               ec.name AS center_name, ec.city AS center_city,
               c.name AS course_name,
               s.exam_date, s.start_time
        FROM bookings_booking b
        JOIN centers_examslot s ON s.id = b.slot_id
        JOIN centers_examcenter ec ON ec.id = s.center_id
        JOIN catalog_course c ON c.id = s.course_id
        WHERE b.id = :booking_id AND b.user_id = :user_id
    """
    row = (
        await db.execute(text(query), {"booking_id": booking_id, "user_id": user_id})
    ).mappings().first()
    if not row:
        return None
    return BookingOut(
        id=row["id"],
        slot_id=row["slot_id"],
        slot_detail=SlotDetail(
            center=row["center_name"],
            city=row["center_city"],
            course=row["course_name"],
            exam_date=row["exam_date"],
            start_time=row["start_time"],
        ),
        student_name=row["student_name"],
        student_dob=row["student_dob"],
        status=row["status"],
        notes=row["notes"] or "",
        created_at=row["created_at"],
    )
