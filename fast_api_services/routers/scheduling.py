"""
FastAPI scheduling router — CENTER_ADMIN REST endpoints.

All endpoints require the caller to have role = CENTER_ADMIN.
Reads are served from the DB directly; writes are proxied to Django.

Routes:
  GET  /api/scheduling/examiners/               — list examiners (with optional filters)
  GET  /api/scheduling/examiners/{id}/load/     — examiner daily load
  GET  /api/scheduling/slots/{slot_id}/suggest-examiners/  — ranked suggestions
  GET  /api/scheduling/calendar/                — exam calendar
  POST /api/scheduling/slots/{slot_id}/assign-examiner/    — assign (proxied to Django)
  POST /api/scheduling/bookings/{booking_id}/reschedule/   — reschedule (proxied to Django)
"""
from __future__ import annotations

import logging
from datetime import date
from typing import Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from fast_api_services.auth import get_current_user
from fast_api_services.config import get_settings
from fast_api_services.database import get_db
from fast_api_services.schemas.models import (
    AssignExaminerIn,
    ExaminerAvailabilityOut,
    ExaminerOut,
    ExamSlotScheduleOut,
    RescheduleBookingIn,
)
from fast_api_services.services.examiner_service import (
    get_exam_calendar,
    get_examiner_daily_load,
    list_examiners,
    suggest_examiners_for_slot,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/scheduling", tags=["scheduling"])


# ── auth guard ────────────────────────────────────────────────────────────────

async def _require_center_admin(current_user=Depends(get_current_user)):
    """Dependency — raises 403 if caller is not CENTER_ADMIN."""
    from sqlalchemy import text
    from fast_api_services.database import get_session_factory

    async with get_session_factory()() as db:
        row = await db.execute(
            text("SELECT role FROM accounts_userprofile WHERE user_id = :uid"),
            {"uid": current_user.user_id},
        )
        profile = row.fetchone()

    if not profile or profile.role != "CENTER_ADMIN":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only CENTER_ADMIN users can access scheduling endpoints.",
        )
    return current_user


# ── read endpoints ────────────────────────────────────────────────────────────

@router.get("/examiners/", response_model=list[ExaminerOut])
async def list_examiners_endpoint(
    center_id: Optional[int] = Query(None),
    available_date: Optional[date] = Query(None),
    style: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    _: object = Depends(_require_center_admin),
):
    """List examiners with optional center / date / style filters."""
    return await list_examiners(db, center_id=center_id, available_date=available_date, style=style)


@router.get("/examiners/{examiner_id}/load/")
async def get_load_endpoint(
    examiner_id: int,
    on_date: date = Query(..., description="YYYY-MM-DD"),
    db: AsyncSession = Depends(get_db),
    _: object = Depends(_require_center_admin),
):
    """Return how many exams an examiner has booked on a specific date."""
    load = await get_examiner_daily_load(db, examiner_id, on_date)
    return {"examiner_id": examiner_id, "date": on_date, "exams_today": load}


@router.get("/slots/{slot_id}/suggest-examiners/", response_model=list[ExaminerAvailabilityOut])
async def suggest_examiners_endpoint(
    slot_id: int,
    db: AsyncSession = Depends(get_db),
    _: object = Depends(_require_center_admin),
):
    """Return ranked examiner suggestions for a slot."""
    return await suggest_examiners_for_slot(db, slot_id)


@router.get("/calendar/", response_model=list[ExamSlotScheduleOut])
async def get_calendar_endpoint(
    center_id: Optional[int] = Query(None),
    date_from: Optional[date] = Query(None),
    date_to: Optional[date] = Query(None),
    db: AsyncSession = Depends(get_db),
    _: object = Depends(_require_center_admin),
):
    """Return the exam calendar for a center."""
    return await get_exam_calendar(db, center_id, date_from, date_to)


# ── write endpoints (proxied to Django) ──────────────────────────────────────

@router.post("/slots/{slot_id}/assign-examiner/")
async def assign_examiner_endpoint(
    slot_id: int,
    payload: AssignExaminerIn,
    current_user=Depends(_require_center_admin),
):
    """Assign an examiner to an exam slot (proxied to Django for transactional write)."""
    if not payload.confirm:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="confirm must be true to execute this action.",
        )
    settings = get_settings()
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.post(
            f"{settings.django_service_url}/api/centers/slots/{slot_id}/assign-examiner/",
            json={"examiner_id": payload.examiner_id},
            headers={"Authorization": f"Bearer {current_user.raw_token}"},
        )
    if resp.status_code in (200, 201):
        return resp.json()
    raise HTTPException(status_code=resp.status_code, detail=resp.text[:300])


@router.post("/bookings/{booking_id}/reschedule/")
async def reschedule_booking_endpoint(
    booking_id: int,
    payload: RescheduleBookingIn,
    current_user=Depends(get_current_user),
):
    """Reschedule a booking (proxied to Django for atomic swap)."""
    if not payload.confirm:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="confirm must be true to execute this action.",
        )
    settings = get_settings()
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.post(
            f"{settings.django_service_url}/api/bookings/{booking_id}/reschedule/",
            json={"new_slot_id": payload.new_slot_id, "reason": payload.reason or ""},
            headers={"Authorization": f"Bearer {current_user.raw_token}"},
        )
    if resp.status_code in (200, 201):
        return resp.json()
    raise HTTPException(status_code=resp.status_code, detail=resp.text[:300])
