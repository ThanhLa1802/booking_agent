"""Celery tasks for outbound notifications (MOCK delivery)."""
from __future__ import annotations

import logging

from celery import shared_task
from django.utils import timezone

from .models import Notification, NotificationStatus
from .providers import get_provider

logger = logging.getLogger(__name__)


@shared_task(name="notifications.tasks.dispatch_notification")
def dispatch_notification(notification_id: int) -> str:
    """Send one queued notification through its provider (mock → log only)."""
    try:
        notification = Notification.objects.get(pk=notification_id)
    except Notification.DoesNotExist:
        logger.warning("dispatch_notification: %s not found", notification_id)
        return "missing"

    if notification.status == NotificationStatus.SENT:
        return "already-sent"

    provider = get_provider(notification.channel)
    ok = provider.send(
        notification.recipient or "(no recipient)",
        notification.subject,
        notification.body,
    )

    notification.status = NotificationStatus.SENT if ok else NotificationStatus.FAILED
    notification.sent_at = timezone.now() if ok else None
    notification.error = "" if ok else "provider returned failure"
    notification.save(update_fields=["status", "sent_at", "error"])
    return notification.status


@shared_task(name="notifications.tasks.dispatch_queued")
def dispatch_queued() -> int:
    """Retry sweep for notifications stuck in QUEUED (e.g. broker was down)."""
    queued = Notification.objects.filter(status=NotificationStatus.QUEUED)
    count = 0
    for n in queued:
        dispatch_notification(n.pk)
        count += 1
    return count


@shared_task(name="notifications.tasks.send_exam_reminders")
def send_exam_reminders(days_ahead: int = 3) -> int:
    """
    Send reminders for exams happening in ``days_ahead`` days.

    Scheduled daily via CELERY_BEAT_SCHEDULE.
    """
    from datetime import timedelta

    from bookings.models import Booking, BookingStatus

    target = timezone.now().date() + timedelta(days=days_ahead)
    bookings = Booking.objects.filter(
        status__in=[BookingStatus.PAID, BookingStatus.CONFIRMED],
        slot__exam_date=target,
    ).select_related("slot__center", "slot__course")

    from .services import notify_exam_reminder

    count = 0
    for booking in bookings:
        notify_exam_reminder(booking)
        count += 1
    return count
