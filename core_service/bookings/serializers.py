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
