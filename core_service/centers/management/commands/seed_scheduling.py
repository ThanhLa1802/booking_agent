"""
Management command: seed mock scheduling data for local testing.

Usage:
    python manage.py seed_scheduling

What it creates:
  1. Superuser: superadmin / Admin@1234
  2. Links admin1 → ExamCenter 1 (Trinity Hanoi Center)
  3. 4 Examiners at Center 1 with specializations
  4. 1 Examiner unavailability for Nguyen Thi Mai: 2026-05-15 to 2026-05-16
  5. 8 future ExamSlots (May–June 2026) at Center 1
  6. Pre-assigns examiners to 4 slots to populate the calendar view
"""

import datetime

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand

from catalog.models import Course, Instrument
from centers.models import ExamCenter, ExamSlot, Examiner, ExaminerUnavailability


class Command(BaseCommand):
    help = "Seed mock data for scheduling tests"

    def handle(self, *args, **options):
        self._create_superuser()
        center = self._link_admin_to_center()
        examiners = self._create_examiners(center)
        self._create_unavailability(examiners)
        slots = self._create_slots(center)
        self._assign_examiners(slots, examiners)
        self.stdout.write(self.style.SUCCESS("\n✅ Scheduling mock data seeded successfully."))

    # ──────────────────────────────────────────────────────────────

    def _create_superuser(self):
        if not User.objects.filter(username="superadmin").exists():
            User.objects.create_superuser("superadmin", "superadmin@trinity.com", "Admin@1234")
            self.stdout.write("  Created superuser: superadmin / Admin@1234")
        else:
            self.stdout.write("  Superuser already exists: superadmin")

    def _link_admin_to_center(self):
        center = ExamCenter.objects.get(pk=1)
        try:
            admin_user = User.objects.get(username="admin1")
            center.admin_user = admin_user
            center.save()
            self.stdout.write(f"  Linked admin1 → {center.name}")
        except User.DoesNotExist:
            self.stdout.write(self.style.WARNING("  admin1 not found — skipping center link"))
        return center

    def _create_examiners(self, center):
        piano = Instrument.objects.filter(name="Piano").first()
        violin = Instrument.objects.filter(name="Violin").first()
        guitar_classical = Instrument.objects.filter(name="Guitar", style="CLASSICAL_JAZZ").first()
        guitar_rock = Instrument.objects.filter(name="Guitar", style="ROCK_POP").first()
        vocals = Instrument.objects.filter(name="Vocals").first()

        specs = [
            ("Nguyen Thi Mai", "mai@trinity.vn", "0901000001", 6, [piano, violin]),
            ("Tran Van Duc", "duc@trinity.vn", "0901000002", 8, [guitar_classical, guitar_rock]),
            ("Le Minh Hoa", "hoa@trinity.vn", "0901000003", 5, [piano, vocals]),
            ("Pham Quoc Bao", "bao@trinity.vn", "0901000004", 8, [violin, guitar_classical]),
        ]

        examiners = []
        for name, email, phone, max_e, instruments in specs:
            e, created = Examiner.objects.get_or_create(
                email=email,
                defaults={
                    "center": center,
                    "name": name,
                    "phone": phone,
                    "max_exams_per_day": max_e,
                    "is_active": True,
                },
            )
            if created:
                valid_instruments = [i for i in instruments if i]
                e.specializations.set(valid_instruments)
                self.stdout.write(f"  Created examiner: {name}")
            else:
                self.stdout.write(f"  Examiner exists: {name}")
            examiners.append(e)

        return examiners

    def _create_unavailability(self, examiners):
        mai = examiners[0]
        _, created = ExaminerUnavailability.objects.get_or_create(
            examiner=mai,
            date_from=datetime.date(2026, 5, 15),
            date_to=datetime.date(2026, 5, 16),
            defaults={"reason": "Nghỉ phép cá nhân"},
        )
        if created:
            self.stdout.write(
                f"  Unavailability: {mai.name} off 2026-05-15 – 2026-05-16"
            )

    def _create_slots(self, center):
        courses = list(Course.objects.filter(is_active=True)[:8])
        if not courses:
            self.stdout.write(self.style.WARNING("  No courses found — skipping slot creation"))
            return []

        slot_data = [
            # (exam_date, start_time, course_idx, capacity)
            (datetime.date(2026, 5, 10), datetime.time(9, 0),  0, 4),
            (datetime.date(2026, 5, 10), datetime.time(10, 0), 1, 3),
            (datetime.date(2026, 5, 10), datetime.time(11, 0), 2, 5),
            (datetime.date(2026, 5, 15), datetime.time(9, 0),  3, 4),  # Mai unavailable on this day
            (datetime.date(2026, 5, 15), datetime.time(14, 0), 0, 3),
            (datetime.date(2026, 5, 20), datetime.time(9, 0),  1, 6),
            (datetime.date(2026, 5, 20), datetime.time(13, 0), 4, 4),
            (datetime.date(2026, 6, 5),  datetime.time(9, 0),  2, 5),
        ]

        slots = []
        for exam_date, start_time, course_idx, capacity in slot_data:
            course = courses[course_idx % len(courses)]
            slot, created = ExamSlot.objects.get_or_create(
                center=center,
                course=course,
                exam_date=exam_date,
                start_time=start_time,
                defaults={
                    "capacity": capacity,
                    "reserved_count": 0,
                    "is_active": True,
                },
            )
            if created:
                self.stdout.write(
                    f"  Created slot: {course.name} on {exam_date} {start_time}"
                )
            slots.append(slot)

        return slots

    def _assign_examiners(self, slots, examiners):
        """Pre-assign examiners to first 4 slots to populate calendar view."""
        if not slots or not examiners:
            return
        assignments = [
            (slots[0], examiners[0]),  # Mai → 2026-05-10 09:00
            (slots[1], examiners[1]),  # Duc → 2026-05-10 10:00
            (slots[2], examiners[2]),  # Hoa → 2026-05-10 11:00
            (slots[4], examiners[1]),  # Duc → 2026-05-15 14:00 (Mai unavailable that day)
        ]
        for slot, examiner in assignments:
            if slot.examiner_id is None:
                slot.examiner = examiner
                slot.save(update_fields=["examiner"])
                self.stdout.write(
                    f"  Assigned {examiner.name} → {slot.exam_date} {slot.start_time}"
                )
