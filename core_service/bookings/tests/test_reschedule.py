"""
TDD tests for the atomic reschedule endpoint.
POST /api/bookings/{pk}/reschedule/

Tests must FAIL until the endpoint is implemented.
"""
import datetime

import pytest
from django.contrib.auth.models import User
from rest_framework.test import APIClient


# ── helpers ──────────────────────────────────────────────────────────────────

def _make_user(username="student1", role="STUDENT"):
    from accounts.models import UserProfile
    user = User.objects.create_user(username=username, password="testpass123")
    UserProfile.objects.create(user=user, role=role)
    return user


def _make_instrument(name="Piano", style="CLASSICAL_JAZZ"):
    from catalog.models import Instrument
    return Instrument.objects.get_or_create(name=name, style=style)[0]


def _make_course(instrument, grade=1):
    from catalog.models import Course
    return Course.objects.get_or_create(
        instrument=instrument,
        grade=grade,
        defaults={"name": f"{instrument.name} G{grade}", "duration_minutes": 10, "fee": 800000},
    )[0]


def _make_center(name="Center A", city="Hanoi"):
    from centers.models import ExamCenter
    return ExamCenter.objects.create(name=name, city=city, address="1 Test St")


def _make_slot(center, course, exam_date, start_time, capacity=5, reserved=0):
    from centers.models import ExamSlot
    return ExamSlot.objects.create(
        center=center,
        course=course,
        exam_date=exam_date,
        start_time=start_time,
        capacity=capacity,
        reserved_count=reserved,
    )


def _make_booking(user, slot, student_name="Nguyen Van A"):
    from bookings.models import Booking, BookingStatus
    slot.reserved_count += 1
    slot.save(update_fields=["reserved_count"])
    return Booking.objects.create(
        user=user,
        slot=slot,
        student_name=student_name,
        student_dob=datetime.date(2010, 1, 1),
        status=BookingStatus.CONFIRMED,
    )


# ── reschedule tests ──────────────────────────────────────────────────────────

@pytest.mark.django_db
class TestRescheduleEndpoint:
    def setup_method(self):
        self.client = APIClient()
        self.instrument = _make_instrument()
        self.course = _make_course(self.instrument)
        self.center = _make_center()
        self.user = _make_user()

    def _auth(self, user=None):
        u = user or self.user
        self.client.force_authenticate(user=u)

    def test_reschedule_success_moves_slot(self):
        old_slot = _make_slot(
            self.center, self.course,
            datetime.date(2026, 6, 1), datetime.time(9, 0),
            capacity=2, reserved=0,
        )
        new_slot = _make_slot(
            self.center, self.course,
            datetime.date(2026, 6, 5), datetime.time(10, 0),
            capacity=3, reserved=0,
        )
        booking = _make_booking(self.user, old_slot)
        self._auth()

        resp = self.client.post(
            f"/api/bookings/{booking.pk}/reschedule/",
            {"new_slot_id": new_slot.pk, "reason": "Schedule conflict"},
            format="json",
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["slot"] == new_slot.pk

    def test_reschedule_decrements_old_slot(self):
        old_slot = _make_slot(
            self.center, self.course,
            datetime.date(2026, 6, 1), datetime.time(9, 0),
            capacity=3, reserved=0,
        )
        new_slot = _make_slot(
            self.center, self.course,
            datetime.date(2026, 6, 5), datetime.time(9, 0),
            capacity=3, reserved=0,
        )
        booking = _make_booking(self.user, old_slot)
        old_reserved_before = old_slot.reserved_count
        self._auth()

        self.client.post(
            f"/api/bookings/{booking.pk}/reschedule/",
            {"new_slot_id": new_slot.pk},
            format="json",
        )
        old_slot.refresh_from_db()
        assert old_slot.reserved_count == old_reserved_before - 1

    def test_reschedule_increments_new_slot(self):
        old_slot = _make_slot(
            self.center, self.course,
            datetime.date(2026, 6, 1), datetime.time(9, 0),
        )
        new_slot = _make_slot(
            self.center, self.course,
            datetime.date(2026, 6, 5), datetime.time(9, 0),
            capacity=3, reserved=0,
        )
        booking = _make_booking(self.user, old_slot)
        self._auth()

        self.client.post(
            f"/api/bookings/{booking.pk}/reschedule/",
            {"new_slot_id": new_slot.pk},
            format="json",
        )
        new_slot.refresh_from_db()
        assert new_slot.reserved_count == 1

    def test_reschedule_fails_when_new_slot_full(self):
        old_slot = _make_slot(
            self.center, self.course,
            datetime.date(2026, 6, 1), datetime.time(9, 0),
        )
        full_slot = _make_slot(
            self.center, self.course,
            datetime.date(2026, 6, 5), datetime.time(9, 0),
            capacity=2, reserved=2,  # already full
        )
        booking = _make_booking(self.user, old_slot)
        self._auth()

        resp = self.client.post(
            f"/api/bookings/{booking.pk}/reschedule/",
            {"new_slot_id": full_slot.pk},
            format="json",
        )
        assert resp.status_code == 409

    def test_reschedule_fails_for_cancelled_booking(self):
        from bookings.models import BookingStatus
        old_slot = _make_slot(
            self.center, self.course,
            datetime.date(2026, 6, 1), datetime.time(9, 0),
        )
        new_slot = _make_slot(
            self.center, self.course,
            datetime.date(2026, 6, 5), datetime.time(9, 0),
        )
        booking = _make_booking(self.user, old_slot)
        booking.status = BookingStatus.CANCELLED
        booking.save(update_fields=["status"])
        self._auth()

        resp = self.client.post(
            f"/api/bookings/{booking.pk}/reschedule/",
            {"new_slot_id": new_slot.pk},
            format="json",
        )
        assert resp.status_code == 400

    def test_reschedule_requires_authentication(self):
        old_slot = _make_slot(
            self.center, self.course,
            datetime.date(2026, 6, 1), datetime.time(9, 0),
        )
        new_slot = _make_slot(
            self.center, self.course,
            datetime.date(2026, 6, 5), datetime.time(9, 0),
        )
        booking = _make_booking(self.user, old_slot)

        resp = self.client.post(
            f"/api/bookings/{booking.pk}/reschedule/",
            {"new_slot_id": new_slot.pk},
            format="json",
        )
        assert resp.status_code == 401

    def test_other_user_cannot_reschedule(self):
        other_user = _make_user(username="other_student")
        old_slot = _make_slot(
            self.center, self.course,
            datetime.date(2026, 6, 1), datetime.time(9, 0),
        )
        new_slot = _make_slot(
            self.center, self.course,
            datetime.date(2026, 6, 5), datetime.time(9, 0),
        )
        booking = _make_booking(self.user, old_slot)
        self._auth(user=other_user)

        resp = self.client.post(
            f"/api/bookings/{booking.pk}/reschedule/",
            {"new_slot_id": new_slot.pk},
            format="json",
        )
        assert resp.status_code == 404

    def test_reschedule_same_slot_is_rejected(self):
        slot = _make_slot(
            self.center, self.course,
            datetime.date(2026, 6, 1), datetime.time(9, 0),
        )
        booking = _make_booking(self.user, slot)
        self._auth()

        resp = self.client.post(
            f"/api/bookings/{booking.pk}/reschedule/",
            {"new_slot_id": slot.pk},
            format="json",
        )
        assert resp.status_code == 400
