from django.db import models
from django.contrib.auth.models import User


class BookingStatus(models.TextChoices):
    PENDING = "PENDING", "Pending"
    CONFIRMED = "CONFIRMED", "Confirmed"
    CANCELLED = "CANCELLED", "Cancelled"


class Booking(models.Model):
    user = models.ForeignKey(User, on_delete=models.PROTECT, related_name="bookings")
    slot = models.ForeignKey(
        "centers.ExamSlot", on_delete=models.PROTECT, related_name="bookings"
    )
    student_name = models.CharField(max_length=200)
    student_dob = models.DateField()
    status = models.CharField(
        max_length=20, choices=BookingStatus.choices, default=BookingStatus.PENDING
    )
    notes = models.TextField(blank=True)
    # Cancellation / rescheduling tracking
    cancelled_at = models.DateTimeField(null=True, blank=True)
    cancellation_reason = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    version = models.PositiveIntegerField(default=0)  # optimistic lock

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Booking #{self.pk} — {self.student_name} — {self.slot}"
