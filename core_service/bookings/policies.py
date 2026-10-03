"""
Booking business policies — cancellation, refund and rescheduling windows.

Pure functions (no ORM, no I/O) so they are trivially unit-testable and can be
reused by serializers, views, Celery tasks and the AI agent.

MOCK NOTE: the numbers below are placeholders pending the real Trinity VN
policy document. They are read from Django settings when available so ops can
tune them without a code change.
"""
from __future__ import annotations

import datetime
from dataclasses import dataclass
from decimal import Decimal

from django.conf import settings

# ── windows (days before the exam date) ───────────────────────────────────────

def _setting(name: str, default: int) -> int:
    return int(getattr(settings, name, default))


def full_refund_days() -> int:
    return _setting("CANCEL_FULL_REFUND_DAYS", 30)


def partial_refund_days() -> int:
    return _setting("CANCEL_PARTIAL_REFUND_DAYS", 7)


def partial_refund_pct() -> int:
    return _setting("CANCEL_PARTIAL_REFUND_PCT", 50)


def reschedule_deadline_days() -> int:
    return _setting("RESCHEDULE_DEADLINE_DAYS", 7)


def max_reschedules() -> int:
    return _setting("MAX_RESCHEDULES", 2)


@dataclass(frozen=True)
class PolicyDecision:
    allowed: bool
    reason: str = ""


def _today(today: datetime.date | None) -> datetime.date:
    if today is not None:
        return today
    from django.utils import timezone

    return timezone.now().date()


def days_until_exam(
    exam_date: datetime.date, today: datetime.date | None = None
) -> int:
    return (exam_date - _today(today)).days


# ── cancellation ──────────────────────────────────────────────────────────────


def refund_percentage(
    exam_date: datetime.date, today: datetime.date | None = None
) -> int:
    """Percentage of the fee refunded if cancelled today."""
    remaining = days_until_exam(exam_date, today)
    if remaining >= full_refund_days():
        return 100
    if remaining >= partial_refund_days():
        return partial_refund_pct()
    return 0


def compute_refund_amount(
    price: Decimal,
    exam_date: datetime.date,
    today: datetime.date | None = None,
) -> Decimal:
    pct = refund_percentage(exam_date, today)
    if pct <= 0:
        return Decimal("0")
    return (Decimal(price) * Decimal(pct) / Decimal(100)).quantize(Decimal("1"))


def can_cancel(
    exam_date: datetime.date, today: datetime.date | None = None
) -> PolicyDecision:
    remaining = days_until_exam(exam_date, today)
    if remaining < 0:
        return PolicyDecision(False, "The exam date has already passed.")
    return PolicyDecision(True)


def can_reschedule(
    exam_date: datetime.date,
    reschedule_count: int = 0,
    today: datetime.date | None = None,
) -> PolicyDecision:
    remaining = days_until_exam(exam_date, today)
    if remaining < 0:
        return PolicyDecision(False, "The exam date has already passed.")
    if remaining < reschedule_deadline_days():
        return PolicyDecision(
            False,
            f"Rescheduling is closed within {reschedule_deadline_days()} days "
            "of the exam date.",
        )
    if reschedule_count >= max_reschedules():
        return PolicyDecision(
            False, f"Maximum of {max_reschedules()} reschedules reached."
        )
    return PolicyDecision(True)
