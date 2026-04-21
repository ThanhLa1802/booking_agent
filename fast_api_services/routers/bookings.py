"""
Bookings router — reads via FastAPI/DB, writes proxied to Django (transactional).
Confirmation gate: POST/DELETE require confirm=True in request body.
"""
from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from httpx import AsyncClient, HTTPStatusError

from fast_api_services.auth import get_current_user, TokenPayload
from fast_api_services.database import get_db
from fast_api_services.schemas.models import (
    BookingOut,
    BookingCreateIn,
    BookingCancelIn,
)
from fast_api_services.services.booking_service import list_user_bookings, get_booking
from fast_api_services.config import get_settings

router = APIRouter(prefix="/bookings", tags=["bookings"])


def _django_client() -> AsyncClient:
    settings = get_settings()
    return AsyncClient(base_url=settings.django_service_url, timeout=10.0)


@router.get("", response_model=list[BookingOut])
async def my_bookings(
    current_user: Annotated[TokenPayload, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
):
    return await list_user_bookings(db, current_user.user_id)


@router.get("/{booking_id}", response_model=BookingOut)
async def booking_detail(
    booking_id: int,
    current_user: Annotated[TokenPayload, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
):
    booking = await get_booking(db, booking_id, current_user.user_id)
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")
    return booking


@router.post("", response_model=BookingOut, status_code=status.HTTP_201_CREATED)
async def create_booking(
    payload: BookingCreateIn,
    current_user: Annotated[TokenPayload, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
):
    # ── Confirmation gate ──────────────────────────────────────────────────────
    if not payload.confirm:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                "Please confirm your booking by setting confirm=true. "
                f"Slot {payload.slot_id} for {payload.student_name} on {payload.student_dob}."
            ),
        )

    # ── Proxy write to Django (Django handles select_for_update + atomic) ──────
    try:
        async with _django_client() as client:
            resp = await client.post(
                "/api/bookings/",
                json={
                    "slot_id": payload.slot_id,
                    "student_name": payload.student_name,
                    "student_dob": str(payload.student_dob),
                    "notes": payload.notes,
                },
                headers={"Authorization": f"Bearer {current_user.raw_token}"},
            )
            resp.raise_for_status()
            data = resp.json()
    except HTTPStatusError as exc:
        raise HTTPException(
            status_code=exc.response.status_code,
            detail=exc.response.json(),
        ) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail="Booking service unavailable") from exc

    booking = await get_booking(db, data["id"], current_user.user_id)
    if not booking:
        raise HTTPException(status_code=500, detail="Booking created but could not be read back")
    return booking


@router.post("/{booking_id}/cancel", response_model=BookingOut)
async def cancel_booking(
    booking_id: int,
    payload: BookingCancelIn,
    current_user: Annotated[TokenPayload, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
):
    # ── Confirmation gate ──────────────────────────────────────────────────────
    if not payload.confirm:
        booking = await get_booking(db, booking_id, current_user.user_id)
        if not booking:
            raise HTTPException(status_code=404, detail="Booking not found")
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                f"Please confirm cancellation of booking #{booking_id} "
                f"({booking.slot_detail.course} on {booking.slot_detail.exam_date}) "
                "by setting confirm=true."
            ),
        )

    try:
        async with _django_client() as client:
            resp = await client.post(
                f"/api/bookings/{booking_id}/cancel/",
                json={"reason": payload.reason},
                headers={"Authorization": f"Bearer {current_user.raw_token}"},
            )
            resp.raise_for_status()
    except HTTPStatusError as exc:
        raise HTTPException(
            status_code=exc.response.status_code,
            detail=exc.response.json(),
        ) from exc

    booking = await get_booking(db, booking_id, current_user.user_id)
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found after cancel")
    return booking
