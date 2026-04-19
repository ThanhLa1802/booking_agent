"""
Read-only Pydantic/SQLModel schemas that map to the Django-managed tables.
FastAPI only reads; Django owns all writes and migrations.
"""
from datetime import date, time, datetime
from decimal import Decimal
from typing import Optional
from pydantic import BaseModel


# ── Catalog ───────────────────────────────────────────────────────────────────

class InstrumentOut(BaseModel):
    id: int
    name: str
    style: str
    style_display: str

    model_config = {"from_attributes": True}


class CourseOut(BaseModel):
    id: int
    instrument_id: int
    instrument_name: str
    style: str
    style_display: str
    grade: int
    name: str
    description: str
    duration_minutes: int
    fee: Decimal

    model_config = {"from_attributes": True}


# ── Centers ───────────────────────────────────────────────────────────────────

class ExamCenterOut(BaseModel):
    id: int
    name: str
    city: str
    address: str
    phone: str
    email: str

    model_config = {"from_attributes": True}


class ExamSlotOut(BaseModel):
    id: int
    center_id: int
    center_name: str
    center_city: str
    course_id: int
    course_name: str
    exam_date: date
    start_time: time
    capacity: int
    available_capacity: int

    model_config = {"from_attributes": True}


# ── Bookings ──────────────────────────────────────────────────────────────────

class SlotDetail(BaseModel):
    center: str
    city: str
    course: str
    exam_date: date
    start_time: time


class BookingOut(BaseModel):
    id: int
    slot_id: int
    slot_detail: SlotDetail
    student_name: str
    student_dob: date
    status: str
    notes: str
    created_at: datetime

    model_config = {"from_attributes": True}


class BookingCreateIn(BaseModel):
    slot_id: int
    student_name: str
    student_dob: date
    notes: str = ""
    confirm: bool = False   # confirmation gate — must be True to proceed


class BookingCancelIn(BaseModel):
    reason: str = ""
    confirm: bool = False
