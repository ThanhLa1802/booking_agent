"""
Bookings router — reads via FastAPI/DB, writes proxied to Django (transactional).
Confirmation gate: POST/DELETE require confirm=True in request body.
"""
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from httpx import AsyncClient, HTTPStatusError
from sqlalchemy.ext.asyncio import AsyncSession

from fast_api_services.auth import TokenPayload, get_current_user
from fast_api_services.config import get_settings
from fast_api_services.database import get_db
from fast_api_services.schemas.models import (
    BookingCancelIn,
    BookingCreateIn,
    BookingOut,
    CandidateDocumentIn,
    CandidateDocumentOut,
    ExamResultOut,
    PaymentInitIn,
    RefundIn,
)
from fast_api_services.services.booking_service import get_booking, list_user_bookings

router = APIRouter(prefix="/bookings", tags=["bookings"])


def _django_client() -> AsyncClient:
    settings = get_settings()
    return AsyncClient(base_url=settings.django_service_url, timeout=10.0)


async def _proxy_post(path: str, *, token: str, json: dict, headers: dict | None = None):
    try:
        async with _django_client() as client:
            resp = await client.post(
                path,
                json=json,
                headers={"Authorization": f"Bearer {token}", **(headers or {})},
            )
            resp.raise_for_status()
            return resp.json()
    except HTTPStatusError as exc:
        raise HTTPException(
            status_code=exc.response.status_code,
            detail=exc.response.json(),
        ) from exc
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=502, detail="Booking service unavailable") from exc


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

    body = {
        "slot_id": payload.slot_id,
        "student_name": payload.student_name,
        "student_dob": str(payload.student_dob),
        "notes": payload.notes,
        "guardian_name": payload.guardian_name,
        "guardian_phone": payload.guardian_phone,
        "contact_email": payload.contact_email,
        "candidate_id_number": payload.candidate_id_number,
        "school": payload.school,
        "teacher_name": payload.teacher_name,
        "special_needs": payload.special_needs,
    }
    extra_headers = (
        {"Idempotency-Key": payload.idempotency_key}
        if payload.idempotency_key
        else None
    )
    data = await _proxy_post(
        "/api/bookings/",
        token=current_user.raw_token,
        json=body,
        headers=extra_headers,
    )

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

    await _proxy_post(
        f"/api/bookings/{booking_id}/cancel/",
        token=current_user.raw_token,
        json={"reason": payload.reason},
    )

    booking = await get_booking(db, booking_id, current_user.user_id)
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found after cancel")
    return booking


@router.post("/{booking_id}/pay", response_model=BookingOut)
async def pay_booking(
    booking_id: int,
    payload: PaymentInitIn,
    current_user: Annotated[TokenPayload, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
):
    """MOCK payment — proxies the in-process gateway to Django."""
    if not payload.confirm:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                f"Please confirm payment for booking #{booking_id} by setting "
                "confirm=true. (MOCK gateway — no money moves.)"
            ),
        )

    await _proxy_post(
        f"/api/bookings/{booking_id}/pay/",
        token=current_user.raw_token,
        json={"method": payload.method},
    )
    booking = await get_booking(db, booking_id, current_user.user_id)
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found after pay")
    return booking


@router.post("/{booking_id}/refund", response_model=BookingOut)
async def refund_booking(
    booking_id: int,
    payload: RefundIn,
    current_user: Annotated[TokenPayload, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
):
    """MOCK refund — amount computed from the cancellation policy."""
    if not payload.confirm:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Please confirm refund for booking #{booking_id} by setting confirm=true.",
        )

    await _proxy_post(
        f"/api/bookings/{booking_id}/refund/",
        token=current_user.raw_token,
        json={},
    )
    booking = await get_booking(db, booking_id, current_user.user_id)
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found after refund")
    return booking


@router.post(
    "/{booking_id}/documents",
    response_model=CandidateDocumentOut,
    status_code=status.HTTP_201_CREATED,
)
async def upload_document(
    booking_id: int,
    payload: CandidateDocumentIn,
    current_user: Annotated[TokenPayload, Depends(get_current_user)],
):
    """MOCK document upload — stores a reference string, no file I/O."""
    return await _proxy_post(
        f"/api/bookings/{booking_id}/documents/",
        token=current_user.raw_token,
        json={"doc_type": payload.doc_type, "file_ref": payload.file_ref},
    )


@router.get("/{booking_id}/result", response_model=ExamResultOut)
async def get_result(
    booking_id: int,
    current_user: Annotated[TokenPayload, Depends(get_current_user)],
):
    try:
        async with _django_client() as client:
            resp = await client.get(
                f"/api/bookings/{booking_id}/result/",
                headers={"Authorization": f"Bearer {current_user.raw_token}"},
            )
            resp.raise_for_status()
            return resp.json()
    except HTTPStatusError as exc:
        raise HTTPException(
            status_code=exc.response.status_code,
            detail=exc.response.json(),
        ) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail="Booking service unavailable") from exc
