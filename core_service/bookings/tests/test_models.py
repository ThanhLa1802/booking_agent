import pytest
from bookings.models import BookingStatus


class TestBookingStatusChoices:
    """Pure unit tests — no DB needed."""

    def test_all_statuses_present(self):
        values = [c.value for c in BookingStatus]
        assert "PENDING" in values
        assert "CONFIRMED" in values
        assert "CANCELLED" in values

    def test_status_labels(self):
        assert BookingStatus.PENDING.label == "Pending"
        assert BookingStatus.CONFIRMED.label == "Confirmed"
        assert BookingStatus.CANCELLED.label == "Cancelled"


@pytest.mark.django_db
class TestExamSlotAvailability:
    def test_available_when_capacity_not_reached(self):
        from centers.models import ExamCenter, ExamSlot
        from catalog.models import Instrument, Course, StyleChoice
        import datetime

        instrument = Instrument.objects.create(name="Piano", style=StyleChoice.CLASSICAL_JAZZ)
        course = Course.objects.create(
            instrument=instrument, grade=1, name="Piano G1", duration_minutes=10, fee=800000
        )
        center = ExamCenter.objects.create(
            name="Test Center", city="Hanoi", address="123 Test St"
        )
        slot = ExamSlot.objects.create(
            center=center,
            course=course,
            exam_date=datetime.date(2025, 6, 1),
            start_time=datetime.time(9, 0),
            capacity=3,
            reserved_count=2,
        )
        assert slot.available_capacity == 1
        assert slot.is_available is True

    def test_not_available_when_full(self):
        from centers.models import ExamCenter, ExamSlot
        from catalog.models import Instrument, Course, StyleChoice
        import datetime

        instrument = Instrument.objects.create(name="Violin", style=StyleChoice.CLASSICAL_JAZZ)
        course = Course.objects.create(
            instrument=instrument, grade=2, name="Violin G2", duration_minutes=12, fee=850000
        )
        center = ExamCenter.objects.create(
            name="Full Center", city="HCMC", address="456 Full St"
        )
        slot = ExamSlot.objects.create(
            center=center,
            course=course,
            exam_date=datetime.date(2025, 6, 1),
            start_time=datetime.time(10, 0),
            capacity=2,
            reserved_count=2,
        )
        assert slot.available_capacity == 0
        assert slot.is_available is False
