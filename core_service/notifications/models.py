from django.contrib.auth.models import User
from django.db import models


class NotificationChannel(models.TextChoices):
    EMAIL = "EMAIL", "Email"
    SMS = "SMS", "SMS"
    PUSH = "PUSH", "Push"


class NotificationStatus(models.TextChoices):
    QUEUED = "QUEUED", "Queued"
    SENT = "SENT", "Sent"
    FAILED = "FAILED", "Failed"


class NotificationTemplate(models.TextChoices):
    BOOKING_CONFIRMATION = "BOOKING_CONFIRMATION", "Booking confirmation"
    PAYMENT_RECEIPT = "PAYMENT_RECEIPT", "Payment receipt"
    EXAM_REMINDER = "EXAM_REMINDER", "Exam reminder"
    EXAMINER_ASSIGNED = "EXAMINER_ASSIGNED", "Examiner assigned"
    RESULT_PUBLISHED = "RESULT_PUBLISHED", "Result published"


class Notification(models.Model):
    """
    An outbound message. MOCK: the provider only logs; no email/SMS is sent.

    Rows are always persisted so the flow is observable and schedulable; the
    actual send is performed by ``notifications.tasks.dispatch_notification``.
    """

    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="notifications", null=True, blank=True
    )
    booking = models.ForeignKey(
        "bookings.Booking",
        on_delete=models.SET_NULL,
        related_name="notifications",
        null=True,
        blank=True,
    )
    channel = models.CharField(
        max_length=10, choices=NotificationChannel.choices, default=NotificationChannel.EMAIL
    )
    template = models.CharField(
        max_length=40,
        choices=NotificationTemplate.choices,
        default=NotificationTemplate.BOOKING_CONFIRMATION,
    )
    recipient = models.CharField(max_length=200, blank=True)
    subject = models.CharField(max_length=255, blank=True)
    body = models.TextField(blank=True)
    status = models.CharField(
        max_length=10, choices=NotificationStatus.choices, default=NotificationStatus.QUEUED
    )
    error = models.TextField(blank=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Notification #{self.pk} — {self.template} — {self.status}"
