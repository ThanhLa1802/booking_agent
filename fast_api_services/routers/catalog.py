from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from fast_api_services.database import get_db
from fast_api_services.services.catalog_service import (
    list_instruments,
    list_courses,
    get_course,
    list_available_slots,
)
from fast_api_services.schemas.models import InstrumentOut, CourseOut, ExamSlotOut

router = APIRouter(prefix="/catalog", tags=["catalog"])


@router.get("/instruments", response_model=list[InstrumentOut])
async def get_instruments(
    style: Optional[str] = Query(None, description="CLASSICAL_JAZZ | ROCK_POP | THEORY"),
    db: AsyncSession = Depends(get_db),
):
    return await list_instruments(db, style=style)


@router.get("/courses", response_model=list[CourseOut])
async def get_courses(
    style: Optional[str] = Query(None),
    instrument: Optional[int] = Query(None),
    grade: Optional[int] = Query(None, ge=1, le=8),
    db: AsyncSession = Depends(get_db),
):
    return await list_courses(db, style=style, instrument_id=instrument, grade=grade)


@router.get("/courses/{course_id}", response_model=CourseOut)
async def get_course_detail(
    course_id: int,
    db: AsyncSession = Depends(get_db),
):
    from fastapi import HTTPException
    course = await get_course(db, course_id)
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")
    return course


@router.get("/slots", response_model=list[ExamSlotOut])
async def get_available_slots(
    course: Optional[int] = Query(None),
    center: Optional[int] = Query(None),
    city: Optional[str] = Query(None),
    date_from: Optional[str] = Query(None, description="YYYY-MM-DD"),
    date_to: Optional[str] = Query(None, description="YYYY-MM-DD"),
    db: AsyncSession = Depends(get_db),
):
    return await list_available_slots(
        db,
        course_id=course,
        center_id=center,
        city=city,
        date_from=date_from,
        date_to=date_to,
    )
