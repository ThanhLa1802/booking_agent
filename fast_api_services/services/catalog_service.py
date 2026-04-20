from typing import Optional
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from fast_api_services.schemas.models import InstrumentOut, CourseOut, ExamSlotOut

STYLE_LABELS = {
    "CLASSICAL_JAZZ": "Classical & Jazz",
    "ROCK_POP": "Rock & Pop",
    "THEORY": "Theory of Music",
}


async def list_instruments(
    db: AsyncSession, style: Optional[str] = None
) -> list[InstrumentOut]:
    query = "SELECT id, name, style FROM catalog_instrument WHERE is_active = true"
    params: dict = {}
    if style:
        query += " AND style = :style"
        params["style"] = style
    query += " ORDER BY style, name"
    rows = (await db.execute(text(query), params)).mappings().all()
    return [
        InstrumentOut(
            id=r["id"],
            name=r["name"],
            style=r["style"],
            style_display=STYLE_LABELS.get(r["style"], r["style"]),
        )
        for r in rows
    ]


async def list_courses(
    db: AsyncSession,
    style: Optional[str] = None,
    instrument_id: Optional[int] = None,
    grade: Optional[int] = None,
) -> list[CourseOut]:
    query = """
        SELECT c.id, c.grade, c.name, c.description, c.duration_minutes, c.fee,
               i.id AS instrument_id, i.name AS instrument_name, i.style
        FROM catalog_course c
        JOIN catalog_instrument i ON i.id = c.instrument_id
        WHERE c.is_active = true AND i.is_active = true
    """
    params: dict = {}
    if style:
        query += " AND i.style = :style"
        params["style"] = style
    if instrument_id:
        query += " AND c.instrument_id = :instrument_id"
        params["instrument_id"] = instrument_id
    if grade:
        query += " AND c.grade = :grade"
        params["grade"] = grade
    query += " ORDER BY i.style, i.name, c.grade"
    rows = (await db.execute(text(query), params)).mappings().all()
    return [
        CourseOut(
            id=r["id"],
            instrument_id=r["instrument_id"],
            instrument_name=r["instrument_name"],
            style=r["style"],
            style_display=STYLE_LABELS.get(r["style"], r["style"]),
            grade=r["grade"],
            name=r["name"],
            description=r["description"] or "",
            duration_minutes=r["duration_minutes"],
            fee=r["fee"],
        )
        for r in rows
    ]


async def get_course(db: AsyncSession, course_id: int) -> Optional[CourseOut]:
    query = """
        SELECT c.id, c.grade, c.name, c.description, c.duration_minutes, c.fee,
               i.id AS instrument_id, i.name AS instrument_name, i.style
        FROM catalog_course c
        JOIN catalog_instrument i ON i.id = c.instrument_id
        WHERE c.id = :course_id AND c.is_active = true
    """
    row = (await db.execute(text(query), {"course_id": course_id})).mappings().first()
    if not row:
        return None
    return CourseOut(
        id=row["id"],
        instrument_id=row["instrument_id"],
        instrument_name=row["instrument_name"],
        style=row["style"],
        style_display=STYLE_LABELS.get(row["style"], row["style"]),
        grade=row["grade"],
        name=row["name"],
        description=row["description"] or "",
        duration_minutes=row["duration_minutes"],
        fee=row["fee"],
    )


async def list_available_slots(
    db: AsyncSession,
    course_id: Optional[int] = None,
    center_id: Optional[int] = None,
    city: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
) -> list[ExamSlotOut]:
    query = """
        SELECT s.id, s.exam_date, s.start_time, s.capacity, s.reserved_count,
               s.course_id, s.center_id,
               ec.name AS center_name, ec.city AS center_city,
               c.name AS course_name, c.grade, c.fee,
               i.name AS instrument_name, i.style
        FROM centers_examslot s
        JOIN centers_examcenter ec ON ec.id = s.center_id
        JOIN catalog_course c ON c.id = s.course_id
        JOIN catalog_instrument i ON i.id = c.instrument_id
        WHERE s.is_active = true AND s.reserved_count < s.capacity
    """
    params: dict = {}
    if course_id:
        query += " AND s.course_id = :course_id"
        params["course_id"] = course_id
    if center_id:
        query += " AND s.center_id = :center_id"
        params["center_id"] = center_id
    if city:
        query += " AND LOWER(ec.city) LIKE :city"
        params["city"] = f"%{city.lower()}%"
    if date_from:
        query += " AND s.exam_date >= :date_from"
        params["date_from"] = date_from
    if date_to:
        query += " AND s.exam_date <= :date_to"
        params["date_to"] = date_to
    query += " ORDER BY s.exam_date, s.start_time"
    rows = (await db.execute(text(query), params)).mappings().all()
    return [
        ExamSlotOut(
            id=r["id"],
            center_id=r["center_id"],
            center_name=r["center_name"],
            center_city=r["center_city"],
            course_id=r["course_id"],
            course_name=r["course_name"],
            instrument_name=r["instrument_name"],
            grade=r["grade"],
            style=r["style"],
            style_display=STYLE_LABELS.get(r["style"], r["style"]),
            fee=r["fee"],
            exam_date=r["exam_date"],
            start_time=r["start_time"],
            capacity=r["capacity"],
            available_capacity=r["capacity"] - r["reserved_count"],
        )
        for r in rows
    ]
