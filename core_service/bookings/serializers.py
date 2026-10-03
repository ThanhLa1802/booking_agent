import logging
from datetime import timedelta
from decimal import Decimal

from centers.models import ExamSlot
from django.conf import settings
from django.db import transaction
from django.utils import timezone
from rest_framework import serializers

from .models import (
    Booking,
    BookingStatus,
    CandidateDocument,
    Certificate,
    ExamResult,
    Payment,
    PaymentStatus,
)
from .policies import can_cancel, can_reschedule, compute_refund_amount

logger = logging.getLogger(__name__)


class BookingCreateSerializer(serializers.Serializer):
    slot_id = serializers.IntegerField()
    student_name = serializers.CharField(max_length=200)
    student_dob = serializers.DateField()
    notes = serializers.CharField(required=False, allow_blank=True, default="")
    # candidate profile (mock-expanded)
    guardian_name = serializers.CharField(required=False, allow_blank=True, default="")
    guardian_phone = serializers.CharField(required=False, allow_blank=True, default="")
    contact_email = serializers.EmailField(required=False, allow_blank=True, default="")
    candidate_id_number = serializers.CharField(
        required=False, allow_blank=True, default=""
    )
    school = serializers.CharField(required=False, allow_blank=True, default="")
    teacher_name = serializers.CharField(required=False, allow_blank=True, default="")
    special_needs = serializers.CharField(required=False, allow_blank=True, default="")
    idempotency_key = serializers.CharField(
        required=False, allow_blank=True, allow_null=True, default=None
    )

    def validate_slot_id(self, value):
        try:
            slot = ExamSlot.objects.get(pk=value, is_active=True)
        except ExamSlot.DoesNotExist:
            raise serializers.ValidationError("Slot not found or inactive.")
        if not slot.is_available:
            raise serializers.ValidationError("This exam slot is fully booked.")
        return value

    @transaction.atomic
    def create(self, validated_data):
        user = self.context["request"].user
        slot = ExamSlot.objects.select_for_update().get(pk=validated_data["slot_id"])

        if not slot.is_available:
            raise serializers.ValidationError("Slot just became fully booked.")

        slot.reserved_count += 1
        slot.save(update_fields=["reserved_count"])

        hold_seconds = getattr(settings, "BOOKING_HOLD_TTL_SECONDS", 900)
        return Booking.objects.create(
            user=user,
            slot=slot,
            student_name=validated_data["student_name"],
            student_dob=validated_data["student_dob"],
            notes=validated_data.get("notes", ""),
            status=BookingStatus.PENDING_PAYMENT,
            # price is snapshotted from the course fee at booking time
            price=slot.course.fee,
            currency="VND",
            payment_status=PaymentStatus.INITIATED,
            hold_expires_at=timezone.now() + timedelta(seconds=hold_seconds),
            idempotency_key=validated_data.get("idempotency_key") or None,
            guardian_name=validated_data.get("guardian_name", ""),
            guardian_phone=validated_data.get("guardian_phone", ""),
            contact_email=validated_data.get("contact_email", ""),
            candidate_id_number=validated_data.get("candidate_id_number", ""),
            school=validated_data.get("school", ""),
            teacher_name=validated_data.get("teacher_name", ""),
            special_needs=validated_data.get("special_needs", ""),
        )


class PaymentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Payment
        fields = (
            "id",
            "amount",
            "currency",
            "method",
            "status",
            "provider_ref",
            "is_mock",
            "refund_amount",
            "created_at",
            "paid_at",
            "refunded_at",
        )


class CandidateDocumentSerializer(serializers.ModelSerializer):
    class Meta:
        model = CandidateDocument
        fields = ("id", "doc_type", "file_ref", "status", "uploaded_at")


class ExamResultSerializer(serializers.ModelSerializer):
    class Meta:
        model = ExamResult
        fields = (
            "id",
            "status",
            "mark",
            "grade_awarded",
            "examiner_comment",
            "published_at",
        )


class CertificateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Certificate
        fields = ("id", "serial_number", "file_ref", "issued_at")


class BookingSerializer(serializers.ModelSerializer):
    slot_detail = serializers.SerializerMethodField()
    payments = PaymentSerializer(many=True, read_only=True)
    documents = CandidateDocumentSerializer(many=True, read_only=True)

    class Meta:
        model = Booking
        fields = (
            "id",
            "slot",
            "slot_detail",
            "student_name",
            "student_dob",
            "status",
            "notes",
            "created_at",
            "price",
            "currency",
            "payment_status",
            "hold_expires_at",
            "guardian_name",
            "guardian_phone",
            "contact_email",
            "candidate_id_number",
            "school",
            "teacher_name",
            "special_needs",
            "reschedule_count",
            "payments",
            "documents",
        )

    def get_slot_detail(self, obj):
        return {
            "center": obj.slot.center.name,
            "city": obj.slot.center.city,
            "course": str(obj.slot.course),
            "exam_date": obj.slot.exam_date,
            "start_time": obj.slot.start_time,
        }


class BookingCancelSerializer(serializers.Serializer):
    reason = serializers.CharField(required=False, allow_blank=True, default="")

    @transaction.atomic
    def cancel(self, booking):
        if booking.status == BookingStatus.CANCELLED:
            raise serializers.ValidationError("Booking is already cancelled.")

        if getattr(settings, "BOOKING_POLICY_ENFORCED", True):
            decision = can_cancel(booking.slot.exam_date)
            if not decision.allowed:
                raise serializers.ValidationError(decision.reason)

        slot = ExamSlot.objects.select_for_update().get(pk=booking.slot_id)
        if slot.reserved_count > 0:
            slot.reserved_count -= 1
            slot.save(update_fields=["reserved_count"])

        # Refund (MOCK) if the booking was paid.
        if booking.payment_status == PaymentStatus.PAID:
            payment = booking.payments.filter(status=PaymentStatus.PAID).first()
            if payment is not None:
                amount = compute_refund_amount(booking.price, booking.slot.exam_date)
                if amount > Decimal("0"):
                    from .payments import get_gateway

                    try:
                        get_gateway().refund(payment, amount)
                    except Exception as exc:  # never block cancellation on refund
                        logger.warning("refund failed for booking %s: %s", booking.pk, exc)

        booking.status = BookingStatus.CANCELLED
        booking.cancelled_at = timezone.now()
        booking.cancellation_reason = self.validated_data.get("reason", "")
        booking.version += 1
        booking.save(
            update_fields=[
                "status",
                "cancelled_at",
                "cancellation_reason",
                "version",
                "payment_status",
            ]
        )
        return booking


class BookingRescheduleSerializer(serializers.Serializer):
    new_slot_id = serializers.IntegerField()
    reason = serializers.CharField(required=False, allow_blank=True, default="")

    def validate_new_slot_id(self, value):
        try:
            ExamSlot.objects.get(pk=value, is_active=True)
        except ExamSlot.DoesNotExist:
            raise serializers.ValidationError("New slot not found or inactive.")
        return value

    @transaction.atomic
    def reschedule(self, booking):
        if booking.status == BookingStatus.CANCELLED:
            raise serializers.ValidationError("Cannot reschedule a cancelled booking.")

        if getattr(settings, "BOOKING_POLICY_ENFORCED", True):
            decision = can_reschedule(booking.slot.exam_date, booking.reschedule_count)
            if not decision.allowed:
                raise serializers.ValidationError(decision.reason)

        new_slot_id = self.validated_data["new_slot_id"]
        if booking.slot_id == new_slot_id:
            raise serializers.ValidationError(
                "New slot must be different from the current slot."
            )

        # lock both slots in deterministic order to avoid deadlock
        slot_ids = sorted([booking.slot_id, new_slot_id])
        slots = {
            s.pk: s
            for s in ExamSlot.objects.select_for_update().filter(pk__in=slot_ids)
        }

        old_slot = slots[booking.slot_id]
        new_slot = slots[new_slot_id]

        if not new_slot.is_available:
            raise serializers.ValidationError("The requested slot is fully booked.")

        # atomic swap
        if old_slot.reserved_count > 0:
            old_slot.reserved_count -= 1
            old_slot.save(update_fields=["reserved_count"])

        new_slot.reserved_count += 1
        new_slot.save(update_fields=["reserved_count"])

        booking.slot = new_slot
        booking.notes = (
            f"{booking.notes}\n[Rescheduled: {self.validated_data.get('reason', '')}]"
        ).strip()
        booking.reschedule_count += 1
        booking.version += 1
        booking.save(update_fields=["slot", "notes", "reschedule_count", "version"])
        return booking
