"""
Management command: (re)seed exam slots for a date range.

Usage:
    python manage.py seed_slots                 # current month + next month
    python manage.py seed_slots --clear         # wipe existing slots first
    python manage.py seed_slots --from 2026-10-01 --to 2026-11-30
    python manage.py seed_slots --center 1

Generates realistic slots (Mon–Sat) across every active center, cycling
through active courses. Where eligible examiners exist (matching instrument
specialisation, respecting daily caps and leave), ~70% of slots are assigned
so the admin calendar shows both assigned and unassigned states.
"""

import datetime
import random

from catalog.models import Course
from django.core.management.base import BaseCommand
from django.db import transaction

from centers.models import ExamCenter, Examiner, ExamSlot

START_TIMES = [
    datetime.time(9, 0),
    datetime.time(10, 30),
    datetime.time(14, 0),
    datetime.time(15, 30),
]

RNG_SEED = 42
ASSIGN_RATIO = 0.7  # fraction of eligible slots that get an examiner


def _default_range() -> tuple[datetime.date, datetime.date]:
    """First day of the current month → last day of the next month."""
    today = datetime.date.today()
    start = today.replace(day=1)
    month = start.month + 2
    year = start.year + (month - 1) // 12
    month = (month - 1) % 12 + 1
    end = datetime.date(year, month, 1) - datetime.timedelta(days=1)
    return start, end


class Command(BaseCommand):
    help = "Seed exam slots for a date range (defaults to current + next month)"

    def add_arguments(self, parser):
        parser.add_argument("--from", dest="date_from", help="YYYY-MM-DD (inclusive)")
        parser.add_argument("--to", dest="date_to", help="YYYY-MM-DD (inclusive)")
        parser.add_argument(
            "--center", type=int, default=None, help="Only seed this center id"
        )
        parser.add_argument(
            "--clear",
            action="store_true",
            help="Delete existing slots (and dependent bookings) first",
        )

    def handle(self, *args, **options):
        default_from, default_to = _default_range()
        date_from = self._parse_date(options.get("date_from")) or default_from
        date_to = self._parse_date(options.get("date_to")) or default_to
        if date_to < date_from:
            self.stderr.write(self.style.ERROR("--to must be on or after --from"))
            return

        centers = ExamCenter.objects.filter(is_active=True)
        if options.get("center"):
            centers = centers.filter(pk=options["center"])
        centers = list(centers)

        if not centers:
            self.stderr.write(self.style.ERROR("No active centers found."))
            return

        courses = list(Course.objects.filter(is_active=True))
        if not courses:
            self.stderr.write(self.style.ERROR("No active courses found."))
            return

        if options.get("clear"):
            self._clear(centers)

        rng = random.Random(RNG_SEED)
        created_total = 0
        assigned_total = 0

        for center in centers:
            created, assigned = self._seed_center(
                center, courses, date_from, date_to, rng
            )
            created_total += created
            assigned_total += assigned
            self.stdout.write(
                f"  {center.name}: +{created} slots, {assigned} assigned"
            )

        self.stdout.write(
            self.style.SUCCESS(
                f"\n✅ Seeded {created_total} slots "
                f"({date_from} → {date_to}), {assigned_total} assigned."
            )
        )

    # ── helpers ───────────────────────────────────────────────────────────

    @staticmethod
    def _parse_date(value):
        if not value:
            return None
        return datetime.date.fromisoformat(value)

    def _clear(self, centers):
        from bookings.models import Booking

        center_ids = [c.pk for c in centers]
        bookings = Booking.objects.filter(
            slot__center_id__in=center_ids
        ).delete()[0]
        slots = ExamSlot.objects.filter(center_id__in=center_ids).delete()[0]
        self.stdout.write(
            self.style.WARNING(f"  Cleared {slots} slots and {bookings} bookings.")
        )

    @transaction.atomic
    def _seed_center(self, center, courses, date_from, date_to, rng):
        examiners = list(
            Examiner.objects.filter(center=center, is_active=True).prefetch_related(
                "specializations"
            )
        )
        daily_load: dict[tuple[int, datetime.date], int] = {}

        def pick_examiner(course, day):
            """Return an eligible examiner with remaining daily capacity, or None."""
            eligible = []
            for ex in examiners:
                specs = set(ex.specializations.all())
                if specs and course.instrument_id not in {i.id for i in specs}:
                    continue
                if ex.is_unavailable_on(day):
                    continue
                if daily_load.get((ex.id, day), 0) >= ex.max_exams_per_day:
                    continue
                eligible.append(ex)
            if not eligible:
                return None
            # least-loaded today, ties broken deterministically
            return min(eligible, key=lambda e: daily_load.get((e.id, day), 0))

        created = 0
        assigned = 0
        day = date_from
        day_index = 0
        while day <= date_to:
            if day.weekday() == 6:  # skip Sunday
                day += datetime.timedelta(days=1)
                day_index += 1
                continue

            times = START_TIMES[: 3 + (day_index % 2)]  # 3 or 4 slots/day
            for i, start_time in enumerate(times):
                course = courses[(day_index + i) % len(courses)]
                capacity = 3 + ((day_index + i) % 4)  # 3–6
                reserved = (day_index * 7 + i * 3) % capacity  # 0..capacity-1

                slot = ExamSlot.objects.create(
                    center=center,
                    course=course,
                    exam_date=day,
                    start_time=start_time,
                    capacity=capacity,
                    reserved_count=reserved,
                    is_active=True,
                )
                created += 1

                if rng.random() < ASSIGN_RATIO:
                    examiner = pick_examiner(course, day)
                    if examiner is not None:
                        slot.examiner = examiner
                        slot.save(update_fields=["examiner"])
                        daily_load[(examiner.id, day)] = (
                            daily_load.get((examiner.id, day), 0) + 1
                        )
                        assigned += 1

            day += datetime.timedelta(days=1)
            day_index += 1

        return created, assigned
