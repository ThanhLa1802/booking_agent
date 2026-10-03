"""Unit tests for booking policies — pure functions, no DB."""
import datetime
from decimal import Decimal

from bookings.policies import (
    can_cancel,
    can_reschedule,
    compute_refund_amount,
    days_until_exam,
    refund_percentage,
)

TODAY = datetime.date(2026, 1, 1)


class TestRefund:
    def test_full_refund_outside_30_days(self):
        exam = TODAY + datetime.timedelta(days=45)
        assert refund_percentage(exam, TODAY) == 100
        assert compute_refund_amount(Decimal("800000"), exam, TODAY) == Decimal("800000")

    def test_partial_refund_between_7_and_30_days(self):
        exam = TODAY + datetime.timedelta(days=10)
        assert refund_percentage(exam, TODAY) == 50
        assert compute_refund_amount(Decimal("800000"), exam, TODAY) == Decimal("400000")

    def test_no_refund_within_7_days(self):
        exam = TODAY + datetime.timedelta(days=3)
        assert refund_percentage(exam, TODAY) == 0
        assert compute_refund_amount(Decimal("800000"), exam, TODAY) == Decimal("0")


class TestCancellation:
    def test_can_cancel_future_exam(self):
        assert can_cancel(TODAY + datetime.timedelta(days=1), TODAY).allowed is True

    def test_cannot_cancel_past_exam(self):
        decision = can_cancel(TODAY - datetime.timedelta(days=1), TODAY)
        assert decision.allowed is False


class TestReschedule:
    def test_days_until_exam(self):
        assert days_until_exam(TODAY + datetime.timedelta(days=5), TODAY) == 5

    def test_allowed_when_well_before_deadline(self):
        exam = TODAY + datetime.timedelta(days=30)
        assert can_reschedule(exam, reschedule_count=0, today=TODAY).allowed is True

    def test_blocked_within_deadline(self):
        exam = TODAY + datetime.timedelta(days=2)
        assert can_reschedule(exam, reschedule_count=0, today=TODAY).allowed is False

    def test_blocked_when_max_reschedules_reached(self):
        exam = TODAY + datetime.timedelta(days=30)
        assert can_reschedule(exam, reschedule_count=2, today=TODAY).allowed is False
