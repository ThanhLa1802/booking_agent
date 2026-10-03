from django.contrib.auth.models import User
from django.db import models


class BookingStatus(models.TextChoices):
    PENDING_PAYMENT = "PENDING_PAYMENT", "Pending Payment"
    PENDING = "PENDING", "Pending"
    PAID = "PAID", "Paid"
    CONFIRMED = "CONFIRMED", "Confirmed"
    CANCELLED = "CANCELLED", "Cancelled"


class PaymentStatus(models.TextChoices):
    INITIATED = "INITIATED", "Initiated"
    PAID = "PAID", "Paid"
    FAILED = "FAILED", "Failed"
    REFUNDED = "REFUNDED", "Refunded"
    PARTIALLY_REFUNDED = "PARTIALLY_REFUNDED", "Partially Refunded"


class PaymentMethod(models.TextChoices):
    MOCK = "MOCK", "Mock (dev)"
    VNPAY = "VNPAY", "VNPay"
    MOMO = "MOMO", "MoMo"
    ZALOPAY = "ZALOPAY", "ZaloPay"
    STRIPE = "STRIPE", "Stripe"
    CASH = "CASH", "Cash"


class DocumentType(models.TextChoices):
    ID_CARD = "ID_CARD", "ID Card"
    PASSPORT = "PASSPORT", "Passport"
    PHOTO = "PHOTO", "Photo"
    BIRTH_CERTIFICATE = "BIRTH_CERTIFICATE", "Birth Certificate"
    OTHER = "OTHER", "Other"


class DocumentStatus(models.TextChoices):
    PENDING = "PENDING", "Pending"
    VERIFIED = "VERIFIED", "Verified"
    REJECTED = "REJECTED", "Rejected"


class ResultStatus(models.TextChoices):
    PENDING = "PENDING", "Pending"
    PUBLISHED = "PUBLISHED", "Published"


class Booking(models.Model):
    user = models.ForeignKey(User, on_delete=models.PROTECT, related_name="bookings")
    slot = models.ForeignKey(
        "centers.ExamSlot", on_delete=models.PROTECT, related_name="bookings"
    )
    student_name = models.CharField(max_length=200)
    student_dob = models.DateField()
    status = models.CharField(
        max_length=20, choices=BookingStatus.choices, default=BookingStatus.PENDING_PAYMENT
    )
    notes = models.TextField(blank=True)
    # Cancellation / rescheduling tracking
    cancelled_at = models.DateTimeField(null=True, blank=True)
    cancellation_reason = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    version = models.PositiveIntegerField(default=0)  # optimistic lock

    # ── pricing & payment (mock — gateway wired later) ────────────────────────
    price = models.DecimalField(max_digits=12, decimal_places=0, default=0)
    currency = models.CharField(max_length=8, default="VND")
    payment_status = models.CharField(
        max_length=20,
        choices=PaymentStatus.choices,
        default=PaymentStatus.INITIATED,
    )
    # Reservation hold — the seat is released when this passes without payment.
    hold_expires_at = models.DateTimeField(null=True, blank=True)
    # Client-supplied key so retries of the same confirmation do not double-book.
    idempotency_key = models.CharField(
        max_length=64, null=True, blank=True, unique=True
    )

    # ── candidate profile (mock — expand to full entry form later) ────────────
    guardian_name = models.CharField(max_length=200, blank=True)
    guardian_phone = models.CharField(max_length=20, blank=True)
    contact_email = models.EmailField(blank=True)
    candidate_id_number = models.CharField(max_length=50, blank=True)
    school = models.CharField(max_length=200, blank=True)
    teacher_name = models.CharField(max_length=200, blank=True)
    special_needs = models.TextField(blank=True)
    reschedule_count = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Booking #{self.pk} — {self.student_name} — {self.slot}"

    @property
    def is_hold_expired(self) -> bool:
        from django.utils import timezone

        return bool(
            self.status == BookingStatus.PENDING_PAYMENT
            and self.hold_expires_at
            and self.hold_expires_at < timezone.now()
        )


class Payment(models.Model):
    """A payment attempt against a booking. MOCK provider by default."""

    booking = models.ForeignKey(
        Booking, on_delete=models.CASCADE, related_name="payments"
    )
    amount = models.DecimalField(max_digits=12, decimal_places=0, default=0)
    currency = models.CharField(max_length=8, default="VND")
    method = models.CharField(
        max_length=20, choices=PaymentMethod.choices, default=PaymentMethod.MOCK
    )
    status = models.CharField(
        max_length=20, choices=PaymentStatus.choices, default=PaymentStatus.INITIATED
    )
    provider_ref = models.CharField(max_length=100, blank=True)
    raw_response = models.JSONField(default=dict, blank=True)
    refund_amount = models.DecimalField(max_digits=12, decimal_places=0, default=0)
    is_mock = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    paid_at = models.DateTimeField(null=True, blank=True)
    refunded_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Payment #{self.pk} — booking {self.booking_id} — {self.status}"


class CandidateDocument(models.Model):
    """Uploaded candidate documents. MOCK: stores a reference, not the file."""

    booking = models.ForeignKey(
        Booking, on_delete=models.CASCADE, related_name="documents"
    )
    doc_type = models.CharField(
        max_length=30, choices=DocumentType.choices, default=DocumentType.OTHER
    )
    file_ref = models.CharField(max_length=500, blank=True)
    status = models.CharField(
        max_length=20, choices=DocumentStatus.choices, default=DocumentStatus.PENDING
    )
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-uploaded_at"]

    def __str__(self):
        return f"Document #{self.pk} — booking {self.booking_id} — {self.doc_type}"


class ExamResult(models.Model):
    booking = models.OneToOneField(
        Booking, on_delete=models.CASCADE, related_name="result"
    )
    status = models.CharField(
        max_length=20, choices=ResultStatus.choices, default=ResultStatus.PENDING
    )
    mark = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    grade_awarded = models.CharField(max_length=20, blank=True)
    examiner_comment = models.TextField(blank=True)
    published_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Result — booking {self.booking_id} — {self.status}"


class Certificate(models.Model):
    result = models.OneToOneField(
        ExamResult, on_delete=models.CASCADE, related_name="certificate"
    )
    serial_number = models.CharField(max_length=100, unique=True)
    file_ref = models.CharField(max_length=500, blank=True)
    issued_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Certificate {self.serial_number}"
