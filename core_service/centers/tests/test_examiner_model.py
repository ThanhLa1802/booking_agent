"""
TDD tests for Examiner, ExaminerUnavailability models,
and examiner-aware conflict detection on ExamSlot.
Write tests FIRST — they fail until models are implemented.
"""
import datetime

import pytest
from django.contrib.auth.models import User


# ── helpers ──────────────────────────────────────────────────────────────────

def _make_instrument(name="Piano", style="CLASSICAL_JAZZ"):
    from catalog.models import Instrument
    return Instrument.objects.create(name=name, style=style)


def _make_course(instrument, grade=1):
    from catalog.models import Course
    return Course.objects.create(
        instrument=instrument,
        grade=grade,
        name=f"{instrument.name} G{grade}",
        duration_minutes=10,
        fee=800000,
    )


def _make_center(name="Test Center", city="Hanoi"):
    from centers.models import ExamCenter
    return ExamCenter.objects.create(name=name, city=city, address="123 Test St")


def _make_examiner(center, name="Nguyen Van A", email="a@test.com", max_per_day=3):
    from centers.models import Examiner
    return Examiner.objects.create(
        center=center,
        name=name,
        email=email,
        max_exams_per_day=max_per_day,
        is_active=True,
    )


def _make_slot(center, course, exam_date, start_time, examiner=None, capacity=5):
    from centers.models import ExamSlot
    return ExamSlot.objects.create(
        center=center,
        course=course,
        exam_date=exam_date,
        start_time=start_time,
        capacity=capacity,
        reserved_count=0,
        examiner=examiner,
    )


# ── Examiner model ────────────────────────────────────────────────────────────

@pytest.mark.django_db
class TestExaminerModel:
    def test_create_examiner(self):
        center = _make_center()
        examiner = _make_examiner(center)
        assert examiner.pk is not None
        assert examiner.name == "Nguyen Van A"
        assert examiner.center == center
        assert examiner.is_active is True
        assert examiner.max_exams_per_day == 3

    def test_examiner_str(self):
        center = _make_center()
        examiner = _make_examiner(center, name="Tran Thi B")
        assert "Tran Thi B" in str(examiner)

    def test_examiner_specializations_m2m(self):
        from centers.models import Examiner
        center = _make_center()
        instrument1 = _make_instrument("Piano", "CLASSICAL_JAZZ")
        instrument2 = _make_instrument("Guitar", "ROCK_POP")
        examiner = _make_examiner(center)
        examiner.specializations.add(instrument1, instrument2)
        assert examiner.specializations.count() == 2

    def test_inactive_examiner(self):
        from centers.models import Examiner
        center = _make_center()
        examiner = Examiner.objects.create(
            center=center,
            name="Inactive",
            email="inactive@test.com",
            max_exams_per_day=5,
            is_active=False,
        )
        assert examiner.is_active is False


# ── ExaminerUnavailability ────────────────────────────────────────────────────

@pytest.mark.django_db
class TestExaminerUnavailability:
    def test_create_unavailability(self):
        from centers.models import ExaminerUnavailability
        center = _make_center()
        examiner = _make_examiner(center)
        unavail = ExaminerUnavailability.objects.create(
            examiner=examiner,
            date_from=datetime.date(2026, 5, 1),
            date_to=datetime.date(2026, 5, 7),
            reason="Annual leave",
        )
        assert unavail.pk is not None
        assert unavail.examiner == examiner
        assert unavail.reason == "Annual leave"

    def test_is_unavailable_on_date_in_range(self):
        from centers.models import ExaminerUnavailability
        center = _make_center()
        examiner = _make_examiner(center)
        ExaminerUnavailability.objects.create(
            examiner=examiner,
            date_from=datetime.date(2026, 5, 1),
            date_to=datetime.date(2026, 5, 7),
            reason="Leave",
        )
        # date within range → unavailable
        assert examiner.is_unavailable_on(datetime.date(2026, 5, 4)) is True

    def test_is_available_outside_unavailability_range(self):
        from centers.models import ExaminerUnavailability
        center = _make_center()
        examiner = _make_examiner(center)
        ExaminerUnavailability.objects.create(
            examiner=examiner,
            date_from=datetime.date(2026, 5, 1),
            date_to=datetime.date(2026, 5, 7),
            reason="Leave",
        )
        # date outside range → available
        assert examiner.is_unavailable_on(datetime.date(2026, 5, 10)) is False

    def test_no_unavailability_means_available(self):
        center = _make_center()
        examiner = _make_examiner(center)
        assert examiner.is_unavailable_on(datetime.date(2026, 6, 1)) is False


# ── ExamSlot.examiner FK ──────────────────────────────────────────────────────

@pytest.mark.django_db
class TestExamSlotExaminerFK:
    def test_slot_can_have_no_examiner(self):
        center = _make_center()
        course = _make_course(_make_instrument())
        slot = _make_slot(center, course, datetime.date(2026, 6, 1), datetime.time(9, 0))
        assert slot.examiner is None

    def test_slot_can_be_assigned_examiner(self):
        center = _make_center()
        course = _make_course(_make_instrument())
        examiner = _make_examiner(center)
        slot = _make_slot(
            center, course,
            datetime.date(2026, 6, 1), datetime.time(9, 0),
            examiner=examiner,
        )
        assert slot.examiner == examiner


# ── Examiner daily load + conflict detection ──────────────────────────────────

@pytest.mark.django_db
class TestExaminerDailyLoad:
    def test_daily_load_zero_initially(self):
        center = _make_center()
        course = _make_course(_make_instrument())
        examiner = _make_examiner(center, max_per_day=3)
        load = examiner.daily_load(datetime.date(2026, 6, 1))
        assert load == 0

    def test_daily_load_counts_assigned_slots(self):
        center = _make_center()
        course = _make_course(_make_instrument())
        examiner = _make_examiner(center, max_per_day=3)
        _make_slot(center, course, datetime.date(2026, 6, 1), datetime.time(9, 0), examiner)
        _make_slot(center, course, datetime.date(2026, 6, 1), datetime.time(10, 0), examiner)
        load = examiner.daily_load(datetime.date(2026, 6, 1))
        assert load == 2

    def test_daily_load_does_not_count_other_days(self):
        center = _make_center()
        course = _make_course(_make_instrument())
        examiner = _make_examiner(center, max_per_day=3)
        _make_slot(center, course, datetime.date(2026, 6, 2), datetime.time(9, 0), examiner)
        load = examiner.daily_load(datetime.date(2026, 6, 1))
        assert load == 0

    def test_exceeds_daily_limit(self):
        center = _make_center()
        course = _make_course(_make_instrument())
        examiner = _make_examiner(center, max_per_day=2)
        _make_slot(center, course, datetime.date(2026, 6, 1), datetime.time(9, 0), examiner)
        _make_slot(center, course, datetime.date(2026, 6, 1), datetime.time(10, 0), examiner)
        assert examiner.has_capacity_on(datetime.date(2026, 6, 1)) is False

    def test_has_capacity_when_below_limit(self):
        center = _make_center()
        course = _make_course(_make_instrument())
        examiner = _make_examiner(center, max_per_day=3)
        _make_slot(center, course, datetime.date(2026, 6, 1), datetime.time(9, 0), examiner)
        assert examiner.has_capacity_on(datetime.date(2026, 6, 1)) is True


# ── is_assignable_to_slot convenience method ─────────────────────────────────

@pytest.mark.django_db
class TestExaminerIsAssignable:
    def test_assignable_when_available_and_has_capacity(self):
        center = _make_center()
        course = _make_course(_make_instrument())
        examiner = _make_examiner(center, max_per_day=3)
        slot = _make_slot(center, course, datetime.date(2026, 6, 1), datetime.time(9, 0))
        ok, reason = examiner.is_assignable_to_slot(slot)
        assert ok is True
        assert reason == ""

    def test_not_assignable_when_inactive(self):
        from centers.models import Examiner
        center = _make_center()
        course = _make_course(_make_instrument())
        examiner = Examiner.objects.create(
            center=center, name="X", email="x@t.com", max_exams_per_day=5, is_active=False
        )
        slot = _make_slot(center, course, datetime.date(2026, 6, 1), datetime.time(9, 0))
        ok, reason = examiner.is_assignable_to_slot(slot)
        assert ok is False
        assert "inactive" in reason.lower()

    def test_not_assignable_when_on_leave(self):
        from centers.models import ExaminerUnavailability
        center = _make_center()
        course = _make_course(_make_instrument())
        examiner = _make_examiner(center)
        ExaminerUnavailability.objects.create(
            examiner=examiner,
            date_from=datetime.date(2026, 6, 1),
            date_to=datetime.date(2026, 6, 5),
            reason="Leave",
        )
        slot = _make_slot(center, course, datetime.date(2026, 6, 1), datetime.time(9, 0))
        ok, reason = examiner.is_assignable_to_slot(slot)
        assert ok is False
        assert "unavailable" in reason.lower()

    def test_not_assignable_when_daily_limit_reached(self):
        center = _make_center()
        course = _make_course(_make_instrument())
        examiner = _make_examiner(center, max_per_day=1)
        _make_slot(center, course, datetime.date(2026, 6, 1), datetime.time(9, 0), examiner)
        # second slot on same day → over limit
        slot2 = _make_slot(center, course, datetime.date(2026, 6, 1), datetime.time(11, 0))
        ok, reason = examiner.is_assignable_to_slot(slot2)
        assert ok is False
        assert "limit" in reason.lower()
