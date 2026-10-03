"""
Notification service — build messages and enqueue dispatch.

Business code calls ``notify(...)``; it always persists a Notification row and,
when dispatch is enabled, hands it to Celery. This keeps write paths fast and
test-friendly while the actual delivery is a background concern.
"""
from __future__ import annotations

import logging

from django.conf import settings

from .models import (
    Notification,
    NotificationChannel,
    NotificationStatus,
    NotificationTemplate,
)

logger = logging.getLogger(__name__)


def _recipient_for(booking, user) -> str:
    if booking is not None:
        return booking.contact_email or getattr(user, "email", "") or ""
    return getattr(user, "email", "") or ""


def notify(
    *,
    template: str,
    user=None,
    booking=None,
    channel: str = NotificationChannel.EMAIL,
    recipient: str | None = None,
    subject: str = "",
    body: str = "",
) -> Notification:
    """Create a Notification and (optionally) enqueue its delivery."""
    if not getattr(settings, "NOTIFICATIONS_ENABLED", True):
        # Still return an unsaved-ish object so callers can proceed.
        return Notification(
            user=user,
            booking=booking,
            channel=channel,
            template=template,
            recipient=recipient or _recipient_for(booking, user),
            subject=subject,
            body=body,
            status=NotificationStatus.QUEUED,
        )

    notification = Notification.objects.create(
        user=user,
        booking=booking,
        channel=channel,
        template=template,
        recipient=recipient or _recipient_for(booking, user),
        subject=subject,
        body=body,
        status=NotificationStatus.QUEUED,
    )

    if getattr(settings, "NOTIFICATIONS_DISPATCH_ENABLED", True):
        try:
            from .tasks import dispatch_notification

            dispatch_notification.delay(notification.pk)
        except Exception as exc:  # broker down — row stays QUEUED for the retry sweep
            logger.warning("Could not enqueue notification %s: %s", notification.pk, exc)

    return notification


# ── convenience builders ──────────────────────────────────────────────────────

def notify_booking_confirmation(booking) -> Notification:
    slot = booking.slot
    return notify(
        template=NotificationTemplate.BOOKING_CONFIRMATION,
        user=booking.user,
        booking=booking,
        subject=f"Xác nhận đặt lịch thi — Booking #{booking.pk}",
        body=(
            f"Xin chào {booking.student_name},\n\n"
            f"Lịch thi của bạn tại {slot.center.name} ({slot.center.city}) "
            f"vào {slot.exam_date} lúc {slot.start_time} đã được ghi nhận.\n"
            f"Số booking: #{booking.pk}\n\nTrân trọng."
        ),
    )


def notify_payment_receipt(booking, payment=None) -> Notification:
    amount = payment.amount if payment is not None else booking.price
    return notify(
        template=NotificationTemplate.PAYMENT_RECEIPT,
        user=booking.user,
        booking=booking,
        subject=f"Biên nhận thanh toán — Booking #{booking.pk}",
        body=(
            f"Đã nhận thanh toán {amount} {booking.currency} "
            f"cho booking #{booking.pk}.\nCảm ơn bạn."
        ),
    )


def notify_exam_reminder(booking) -> Notification:
    slot = booking.slot
    return notify(
        template=NotificationTemplate.EXAM_REMINDER,
        user=booking.user,
        booking=booking,
        subject=f"Nhắc lịch thi — Booking #{booking.pk}",
        body=(
            f"Nhắc bạn: lịch thi {slot.course} của {booking.student_name} "
            f"diễn ra ngày {slot.exam_date} lúc {slot.start_time} "
            f"tại {slot.center.name}."
        ),
    )


def notify_examiner_assigned(examiner, slot) -> Notification:
    return notify(
        template=NotificationTemplate.EXAMINER_ASSIGNED,
        user=getattr(examiner, "user", None),
        recipient=examiner.email,
        subject="Phân công ca thi",
        body=(
            f"Bạn được phân công ca {slot.course} ngày {slot.exam_date} "
            f"lúc {slot.start_time} tại {slot.center.name}."
        ),
    )


def notify_result_published(booking, result) -> Notification:
    return notify(
        template=NotificationTemplate.RESULT_PUBLISHED,
        user=booking.user,
        booking=booking,
        subject=f"Kết quả thi — Booking #{booking.pk}",
        body=(
            f"Kết quả thi của {booking.student_name}: "
            f"mark={result.mark}, grade={result.grade_awarded or '—'}."
        ),
    )
