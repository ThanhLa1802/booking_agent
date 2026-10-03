"""Integration tests for the MOCK flows: payment, refund, idempotency, holds."""
import datetime

import pytest
from django.contrib.auth.models import User
from django.utils import timezone
from rest_framework.test import APIClient

# ── helpers ───────────────────────────────────────────────────────────────────

def _make_user(username="student1", role="STUDENT"):
    from accounts.models import UserProfile

    user = User.objects.create_user(username=username, password="testpass123")
    UserProfile.objects.create(user=user, role=role)
    return user


def _make_admin():
    from accounts.models import UserProfile, UserRole
    from centers.models import ExamCenter

    user = User.objects.create_user(username="admin1", password="pass")
    UserProfile.objects.create(user=user, role=UserRole.CENTER_ADMIN)
    center = ExamCenter.objects.create(
        name="Center A", city="Hanoi", address="1 St", admin_user=user
    )
    return user, center


def _make_catalog():
    from catalog.models import Course, Instrument, StyleChoice

    instrument = Instrument.objects.create(name="Piano", style=StyleChoice.CLASSICAL_JAZZ)
    course = Course.objects.create(
        instrument=instrument, grade=1, name="Piano G1", duration_minutes=10, fee=800000
    )
    return course


def _make_slot(course, center, exam_date=None, capacity=3):
    from centers.models import ExamSlot

    return ExamSlot.objects.create(
        center=center,
        course=course,
        exam_date=exam_date or (timezone.now().date() + datetime.timedelta(days=60)),
        start_time=datetime.time(9, 0),
        capacity=capacity,
        reserved_count=0,
    )


def _make_booking(user, slot, status="PENDING_PAYMENT", hold_expires_at=None):
    from bookings.models import Booking, BookingStatus, PaymentStatus

    slot.reserved_count += 1
    slot.save(update_fields=["reserved_count"])
    return Booking.objects.create(
        user=user,
        slot=slot,
        student_name="Nguyen Van A",
        student_dob=datetime.date(2010, 1, 1),
        status=BookingStatus(status),
        payment_status=PaymentStatus.INITIATED,
        price=slot.course.fee,
        hold_expires_at=hold_expires_at,
    )


# ── payment / refund ──────────────────────────────────────────────────────────

@pytest.mark.django_db
class TestPaymentFlow:
    def setup_method(self):
        self.client = APIClient()
        self.user = _make_user()
        self.course = _make_catalog()
        from centers.models import ExamCenter

        self.center = ExamCenter.objects.create(name="C", city="Hanoi", address="a")
        self.slot = _make_slot(self.course, self.center)
        self.booking = _make_booking(self.user, self.slot)
        self.client.force_authenticate(user=self.user)

    def test_pay_marks_booking_and_payment_paid(self):
        from bookings.models import BookingStatus, PaymentStatus

        resp = self.client.post(f"/api/bookings/{self.booking.pk}/pay/", {}, format="json")
        assert resp.status_code == 200

        self.booking.refresh_from_db()
        assert self.booking.status == BookingStatus.PAID
        assert self.booking.payment_status == PaymentStatus.PAID
        assert self.booking.hold_expires_at is None
        assert self.booking.payments.filter(status=PaymentStatus.PAID).exists()

    def test_pay_creates_notification_and_audit(self):
        from auditing.models import AuditLog
        from notifications.models import Notification, NotificationTemplate

        self.client.post(f"/api/bookings/{self.booking.pk}/pay/", {}, format="json")

        assert Notification.objects.filter(
            template=NotificationTemplate.PAYMENT_RECEIPT
        ).exists()
        assert AuditLog.objects.filter(action="booking.paid").exists()

    def test_refund_full_outside_window(self):
        from bookings.models import PaymentStatus

        self.client.post(f"/api/bookings/{self.booking.pk}/pay/", {}, format="json")
        resp = self.client.post(
            f"/api/bookings/{self.booking.pk}/refund/", {}, format="json"
        )
        assert resp.status_code == 200
        payment = self.booking.payments.first()
        payment.refresh_from_db()
        assert payment.status == PaymentStatus.REFUNDED
        assert payment.refund_amount == self.booking.price


# ── idempotency ───────────────────────────────────────────────────────────────

@pytest.mark.django_db
class TestIdempotentCreate:
    def test_repeated_key_returns_same_booking(self):
        from bookings.models import Booking

        client = APIClient()
        user = _make_user()
        course = _make_catalog()
        from centers.models import ExamCenter

        center = ExamCenter.objects.create(name="C", city="Hanoi", address="a")
        slot = _make_slot(course, center)
        client.force_authenticate(user=user)

        payload = {
            "slot_id": slot.pk,
            "student_name": "Le Thi B",
            "student_dob": "2011-02-02",
        }
        first = client.post(
            "/api/bookings/", payload, format="json", HTTP_IDEMPOTENCY_KEY="key-123"
        )
        second = client.post(
            "/api/bookings/", payload, format="json", HTTP_IDEMPOTENCY_KEY="key-123"
        )

        assert first.status_code == 201
        assert second.status_code == 200
        assert first.json()["id"] == second.json()["id"]
        assert Booking.objects.filter(idempotency_key="key-123").count() == 1


# ── hold expiry ───────────────────────────────────────────────────────────────

@pytest.mark.django_db
class TestExpireHolds:
    def test_expired_hold_releases_slot(self):
        from bookings.models import BookingStatus
        from bookings.tasks import expire_unpaid_holds

        user = _make_user()
        course = _make_catalog()
        from centers.models import ExamCenter

        center = ExamCenter.objects.create(name="C", city="Hanoi", address="a")
        slot = _make_slot(course, center, capacity=2)
        booking = _make_booking(
            user,
            slot,
            hold_expires_at=timezone.now() - datetime.timedelta(minutes=1),
        )
        assert slot.reserved_count == 1

        released = expire_unpaid_holds()

        assert released == 1
        slot.refresh_from_db()
        booking.refresh_from_db()
        assert slot.reserved_count == 0
        assert booking.status == BookingStatus.CANCELLED


# ── reports ───────────────────────────────────────────────────────────────────

@pytest.mark.django_db
class TestCenterReport:
    def test_report_requires_center_admin(self):
        client = APIClient()
        user = _make_user()
        client.force_authenticate(user=user)
        resp = client.get("/api/centers/reports/summary/")
        assert resp.status_code == 403

    def test_report_returns_summary(self):
        client = APIClient()
        admin, center = _make_admin()
        client.force_authenticate(user=admin)
        resp = client.get("/api/centers/reports/summary/")
        assert resp.status_code == 200
        assert resp.json()["center_id"] == center.pk
        assert "revenue_paid" in resp.json()
