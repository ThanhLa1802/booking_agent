"""
Celery tasks for bookings.

expire_unpaid_holds:
    Release seats held by PENDING_PAYMENT bookings whose hold window lapsed,
    and mark those bookings cancelled. Scheduled every 5 minutes.
"""
from __future__ import annotations

import logging

from celery import shared_task
from django.db import transaction
from django.utils import timezone

logger = logging.getLogger(__name__)


@shared_task(name="bookings.tasks.expire_unpaid_holds")
def expire_unpaid_holds() -> int:
    from centers.models import ExamSlot

    from .models import Booking, BookingStatus

    now = timezone.now()
    expired_ids = list(
        Booking.objects.filter(
            status=BookingStatus.PENDING_PAYMENT,
            hold_expires_at__lt=now,
        ).values_list("id", flat=True)
    )
    if not expired_ids:
        return 0

    released = 0
    with transaction.atomic():
        bookings = (
            Booking.objects.select_for_update()
            .select_related("slot")
            .filter(id__in=expired_ids)
        )
        for booking in bookings:
            slot = ExamSlot.objects.select_for_update().get(pk=booking.slot_id)
            if slot.reserved_count > 0:
                slot.reserved_count -= 1
                slot.save(update_fields=["reserved_count"])
            booking.status = BookingStatus.CANCELLED
            booking.cancelled_at = now
            booking.cancellation_reason = "Hold expired (payment not received)."
            booking.version += 1
            booking.save(
                update_fields=[
                    "status",
                    "cancelled_at",
                    "cancellation_reason",
                    "version",
                ]
            )
            released += 1

    logger.info("expire_unpaid_holds: released %d hold(s)", released)
    return released
