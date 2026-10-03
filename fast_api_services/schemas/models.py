"""
Read-only Pydantic/SQLModel schemas that map to the Django-managed tables.
FastAPI only reads; Django owns all writes and migrations.
"""
from datetime import date, datetime, time
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
    instrument_name: str
    grade: int
    style: str
    style_display: str
    fee: Decimal
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

    # ── payment / holds / candidate profile (optional for backward compat) ────
    price: Optional[Decimal] = None
    currency: str = "VND"
    payment_status: Optional[str] = None
    hold_expires_at: Optional[datetime] = None
    guardian_name: str = ""
    guardian_phone: str = ""
    contact_email: str = ""
    candidate_id_number: str = ""
    school: str = ""
    teacher_name: str = ""
    special_needs: str = ""
    reschedule_count: int = 0

    model_config = {"from_attributes": True}


class PaymentOut(BaseModel):
    id: int
    amount: Decimal
    currency: str
    method: str
    status: str
    provider_ref: str = ""
    is_mock: bool = True
    refund_amount: Decimal = Decimal("0")
    created_at: datetime
    paid_at: Optional[datetime] = None
    refunded_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class PaymentInitIn(BaseModel):
    method: str = "MOCK"
    confirm: bool = False   # confirmation gate — must be True to proceed


class RefundIn(BaseModel):
    confirm: bool = False


class CandidateDocumentIn(BaseModel):
    doc_type: str = "OTHER"
    file_ref: str = ""


class CandidateDocumentOut(BaseModel):
    id: int
    doc_type: str
    file_ref: str = ""
    status: str
    uploaded_at: datetime

    model_config = {"from_attributes": True}


class ExamResultOut(BaseModel):
    id: int
    status: str
    mark: Optional[Decimal] = None
    grade_awarded: str = ""
    examiner_comment: str = ""
    published_at: Optional[datetime] = None
    certificate: Optional[dict] = None

    model_config = {"from_attributes": True}


class BookingCreateIn(BaseModel):
    slot_id: int
    student_name: str
    student_dob: date
    notes: str = ""
    confirm: bool = False   # confirmation gate — must be True to proceed

    # candidate profile (optional, mock-expanded)
    guardian_name: str = ""
    guardian_phone: str = ""
    contact_email: str = ""
    candidate_id_number: str = ""
    school: str = ""
    teacher_name: str = ""
    special_needs: str = ""
    idempotency_key: Optional[str] = None


class BookingCancelIn(BaseModel):
    reason: str = ""
    confirm: bool = False


# ── Scheduling — Examiners ────────────────────────────────────────────────────

class ExaminerOut(BaseModel):
    id: int
    center_id: int
    center_name: str = ""
    center_city: str = ""
    name: str
    email: str
    phone: str
    specialization_names: list[str]
    max_exams_per_day: int
    is_active: bool

    model_config = {"from_attributes": True}


class ExaminerAvailabilityOut(BaseModel):
    examiner: ExaminerOut
    is_available: bool
    exams_today: int


class ExamSlotScheduleOut(ExamSlotOut):
    """ExamSlotOut extended with the assigned examiner (nullable)."""
    examiner_id: Optional[int] = None
    examiner_name: Optional[str] = None


class ExaminerScheduleOut(BaseModel):
    """One examiner plus the slots assigned to them."""
    examiner: ExaminerOut
    slots: list[ExamSlotScheduleOut]


# ── Scheduling — Reschedule ───────────────────────────────────────────────────

class RescheduleBookingIn(BaseModel):
    new_slot_id: int
    reason: str = ""
    confirm: bool = False


class AssignExaminerIn(BaseModel):
    examiner_id: int
    confirm: bool = False
