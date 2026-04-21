from django.db import transaction
from django.utils import timezone
from rest_framework import serializers
from centers.models import ExamSlot
from .models import Booking, BookingStatus


class BookingCreateSerializer(serializers.Serializer):
    slot_id = serializers.IntegerField()
    student_name = serializers.CharField(max_length=200)
    student_dob = serializers.DateField()
    notes = serializers.CharField(required=False, allow_blank=True, default="")

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

        return Booking.objects.create(
            user=user,
            slot=slot,
            student_name=validated_data["student_name"],
            student_dob=validated_data["student_dob"],
            notes=validated_data.get("notes", ""),
            status=BookingStatus.CONFIRMED,
        )


class BookingSerializer(serializers.ModelSerializer):
    slot_detail = serializers.SerializerMethodField()

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

        slot = ExamSlot.objects.select_for_update().get(pk=booking.slot_id)
        if slot.reserved_count > 0:
            slot.reserved_count -= 1
            slot.save(update_fields=["reserved_count"])

        booking.status = BookingStatus.CANCELLED
        booking.cancelled_at = timezone.now()
        booking.cancellation_reason = self.validated_data.get("reason", "")
        booking.version += 1
        booking.save(update_fields=["status", "cancelled_at", "cancellation_reason", "version"])
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
        booking.version += 1
        booking.save(update_fields=["slot", "notes", "version"])
        return booking
