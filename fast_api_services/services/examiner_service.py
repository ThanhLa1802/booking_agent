"""
FastAPI read-only service for examiner data.
All writes go through Django's transactional endpoints.
"""
from datetime import date as date_type
from typing import Optional

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from fast_api_services.schemas.models import (
    ExaminerAvailabilityOut,
    ExaminerOut,
    ExamSlotScheduleOut,
)

STYLE_LABELS = {
    "CLASSICAL_JAZZ": "Classical & Jazz",
    "ROCK_POP": "Rock & Pop",
    "THEORY": "Theory of Music",
}


# ── helpers ───────────────────────────────────────────────────────────────────


def _row_to_examiner(row) -> ExaminerOut:
    return ExaminerOut(
        id=row["id"],
        center_id=row["center_id"],
        center_name=row.get("center_name") or "",
        center_city=row.get("center_city") or "",
        name=row["name"],
        email=row["email"],
        phone=row["phone"] or "",
        specialization_names=(row["specialization_names"] or "").split(",")
        if row["specialization_names"]
        else [],
        max_exams_per_day=row["max_exams_per_day"],
        is_active=row["is_active"],
    )


# ── public service functions ──────────────────────────────────────────────────


async def list_examiners(
    db: AsyncSession,
    center_id: Optional[int] = None,
    available_date: Optional[date_type] = None,
    style: Optional[str] = None,
) -> list[ExaminerOut]:
    """
    Return examiners, optionally filtered by center, availability on a date,
    and instrument style specialization.
    """
    query = """
        SELECT
            e.id,
            e.center_id,
            ec.name  AS center_name,
            ec.city  AS center_city,
            e.name,
            e.email,
            e.phone,
            e.max_exams_per_day,
            e.is_active,
            STRING_AGG(CONCAT(i.name, ' (', i.style, ')'), ', ') AS specialization_names
        FROM centers_examiner e
        JOIN  centers_examcenter ec ON ec.id = e.center_id
        LEFT JOIN centers_examiner_specializations es ON es.examiner_id = e.id
        LEFT JOIN catalog_instrument i ON i.id = es.instrument_id
        WHERE e.is_active = true
    """
    params: dict = {}

    if center_id:
        query += " AND e.center_id = :center_id"
        params["center_id"] = center_id

    if style:
        query += " AND i.style = :style"
        params["style"] = style

    if available_date:
        # exclude examiners on leave on that date
        query += """
            AND NOT EXISTS (
                SELECT 1 FROM centers_examinerunavailability u
                WHERE u.examiner_id = e.id
                  AND u.date_from <= :avail_date
                  AND u.date_to   >= :avail_date
            )
        """
        params["avail_date"] = available_date

    query += " GROUP BY e.id, ec.name, ec.city ORDER BY ec.city, e.name"
    rows = (await db.execute(text(query), params)).mappings().all()
    return [_row_to_examiner(r) for r in rows]


async def get_examiner_daily_load(
    db: AsyncSession,
    examiner_id: int,
    on_date: date_type,
) -> int:
    """Return the number of slots assigned to this examiner on *on_date*."""
    row = (
        await db.execute(
            text(
                "SELECT COUNT(*) AS cnt FROM centers_examslot "
                "WHERE examiner_id = :eid AND exam_date = :d"
            ),
            {"eid": examiner_id, "d": on_date},
        )
    ).mappings().first()
    return int(row["cnt"]) if row else 0


async def check_examiner_conflicts(
    db: AsyncSession,
    examiner_id: int,
    exam_date: date_type,
    max_exams_per_day: int,
) -> tuple[bool, str]:
    """
    Check whether an examiner can be assigned on *exam_date*.
    Returns (ok: bool, reason: str).
    """
    # check leave
    leave_row = (
        await db.execute(
            text(
                "SELECT 1 FROM centers_examinerunavailability "
                "WHERE examiner_id = :eid "
                "  AND date_from <= :d AND date_to >= :d LIMIT 1"
            ),
            {"eid": examiner_id, "d": exam_date},
        )
    ).first()
    if leave_row:
        return False, f"Examiner is on leave on {exam_date}."

    # check daily cap
    load = await get_examiner_daily_load(db, examiner_id, exam_date)
    if load >= max_exams_per_day:
        return False, f"Examiner has reached the daily limit of {max_exams_per_day} exams."

    return True, ""


async def suggest_examiners_for_slot(
    db: AsyncSession,
    slot_id: int,
) -> list[ExaminerAvailabilityOut]:
    """
    Return examiners for a slot's center who are available on the slot date,
    ranked by ascending daily load (least busy first).
    """
    # fetch slot info
    slot_row = (
        await db.execute(
            text(
                "SELECT s.center_id, s.exam_date, c.instrument_id "
                "FROM centers_examslot s "
                "JOIN catalog_course c ON c.id = s.course_id "
                "WHERE s.id = :sid"
            ),
            {"sid": slot_id},
        )
    ).mappings().first()
    if not slot_row:
        return []

    center_id = slot_row["center_id"]
    exam_date = slot_row["exam_date"]
    instrument_id = slot_row["instrument_id"]

    # all active examiners at the center who specialise in this instrument
    # and are not on leave that day
    query = """
        SELECT
            e.id,
            e.center_id,
            ec.name  AS center_name,
            ec.city  AS center_city,
            e.name,
            e.email,
            e.phone,
            e.max_exams_per_day,
            e.is_active,
            STRING_AGG(CONCAT(i2.name, ' (', i2.style, ')'), ', ') AS specialization_names,
            (
                SELECT COUNT(*) FROM centers_examslot s2
                WHERE s2.examiner_id = e.id AND s2.exam_date = :exam_date
            ) AS exams_today
        FROM centers_examiner e
        JOIN  centers_examcenter ec ON ec.id = e.center_id
        LEFT JOIN centers_examiner_specializations es  ON es.examiner_id = e.id
        LEFT JOIN catalog_instrument i2 ON i2.id = es.instrument_id
        WHERE e.center_id = :center_id
          AND e.is_active = true
          AND es.instrument_id = :instrument_id
          AND NOT EXISTS (
              SELECT 1 FROM centers_examinerunavailability u
              WHERE u.examiner_id = e.id
                AND u.date_from <= :exam_date
                AND u.date_to   >= :exam_date
          )
        GROUP BY e.id, ec.name, ec.city
        HAVING (
            SELECT COUNT(*) FROM centers_examslot s3
            WHERE s3.examiner_id = e.id AND s3.exam_date = :exam_date
        ) < e.max_exams_per_day
        ORDER BY exams_today ASC, e.name ASC
    """
    rows = (
        await db.execute(
            text(query),
            {"center_id": center_id, "exam_date": exam_date, "instrument_id": instrument_id},
        )
    ).mappings().all()

    result = []
    for r in rows:
        examiner = _row_to_examiner(r)
        result.append(
            ExaminerAvailabilityOut(
                examiner=examiner,
                is_available=True,
                exams_today=int(r["exams_today"]),
            )
        )
    return result


async def get_exam_calendar(
    db: AsyncSession,
    center_id: Optional[int] = None,
    date_from: Optional[date_type] = None,
    date_to: Optional[date_type] = None,
) -> list[ExamSlotScheduleOut]:
    """
    Return all slots for a center (including full) with examiner info,
    for the calendar view. When center_id is None, returns slots for all centers.
    """
    query = """
        SELECT
            s.id,
            s.center_id,
            s.exam_date,
            s.start_time,
            s.capacity,
            s.reserved_count,
            s.course_id,
            ec.name AS center_name,
            ec.city AS center_city,
            c.name  AS course_name,
            c.grade,
            c.fee,
            i.name  AS instrument_name,
            i.style,
            e.id    AS examiner_id,
            e.name  AS examiner_name
        FROM centers_examslot s
        JOIN centers_examcenter ec ON ec.id = s.center_id
        JOIN catalog_course     c  ON c.id  = s.course_id
        JOIN catalog_instrument i  ON i.id  = c.instrument_id
        LEFT JOIN centers_examiner e ON e.id = s.examiner_id
        WHERE 1=1
    """
    params: dict = {}
    if center_id:  # 0 or None → no filter (show all centers)
        query += " AND s.center_id = :center_id"
        params["center_id"] = center_id
    if date_from:
        query += " AND s.exam_date >= :date_from"
        params["date_from"] = date_from
    if date_to:
        query += " AND s.exam_date <= :date_to"
        params["date_to"] = date_to
    query += " ORDER BY s.exam_date, s.start_time"

    rows = (await db.execute(text(query), params)).mappings().all()
    return [
        ExamSlotScheduleOut(
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
            examiner_id=r["examiner_id"],
            examiner_name=r["examiner_name"],
        )
        for r in rows
    ]
