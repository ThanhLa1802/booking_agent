"""
Management command: seed a rich examiner (teacher) roster across centers.

Usage:
    python manage.py seed_examiners                # all active centers
    python manage.py seed_examiners --center 1
    python manage.py seed_examiners --clear        # delete seeded examiners first

Creates a deterministic roster of examiners per center, covering every catalog
instrument so the batch scheduler and the manual assign dialog always have
eligible examiners. Idempotent — safe to run repeatedly (keyed by email).
"""
import datetime

from catalog.models import Instrument
from django.core.management.base import BaseCommand
from django.db import transaction

from centers.models import ExamCenter, Examiner, ExaminerUnavailability

# Spec key → (instrument name, style) as defined in fixtures/initial_catalog.json
SPEC_ALIASES = {
    "piano": ("Piano", "CLASSICAL_JAZZ"),
    "violin": ("Violin", "CLASSICAL_JAZZ"),
    "guitar_classical": ("Guitar", "CLASSICAL_JAZZ"),
    "guitar_rock": ("Guitar", "ROCK_POP"),
    "vocals": ("Vocals", "ROCK_POP"),
    "drums": ("Drums", "ROCK_POP"),
    "theory": ("Theory of Music", "THEORY"),
}

# (username, full name, phone, max_exams_per_day, [spec keys], is_active)
ROSTER = [
    ("mai", "Nguyễn Thị Mai", "0901000001", 6, ["piano", "violin"], True),
    ("duc", "Trần Văn Đức", "0901000002", 8, ["guitar_classical", "guitar_rock"], True),
    ("hoa", "Lê Minh Hoa", "0901000003", 5, ["piano", "vocals"], True),
    ("bao", "Phạm Quốc Bảo", "0901000004", 8, ["violin", "guitar_classical"], True),
    ("linh", "Hoàng Thùy Linh", "0901000005", 7, ["vocals", "theory"], True),
    ("son", "Đỗ Ngọc Sơn", "0901000006", 9, ["drums", "guitar_rock"], True),
    ("ha", "Vũ Thanh Hà", "0901000007", 6, ["piano", "theory"], True),
    ("tuan", "Bùi Anh Tuấn", "0901000008", 8, ["guitar_rock", "drums"], True),
    ("thao", "Ngô Phương Thảo", "0901000009", 7, ["piano", "violin", "theory"], True),
    ("phuoc", "Đặng Hữu Phước", "0901000010", 6, ["guitar_classical", "theory"], True),
    ("ly", "Trịnh Khánh Ly", "0901000011", 5, ["vocals", "piano"], True),
    ("nam", "Lâm Hoàng Nam", "0901000012", 9, ["drums", "guitar_rock", "vocals"], True),
    # A couple of inactive records so the UI shows the "Ngưng" state.
    ("an", "Mai Tuấn An", "0901000013", 4, ["piano"], False),
    ("ngoc", "Lý Bảo Ngọc", "0901000014", 4, ["vocals"], False),
]


class Command(BaseCommand):
    help = "Seed a rich examiner roster across active centers"

    def add_arguments(self, parser):
        parser.add_argument(
            "--center", type=int, default=None, help="Only seed this center id"
        )
        parser.add_argument(
            "--clear",
            action="store_true",
            help="Delete existing examiners (and their leave) for the target centers",
        )

    def handle(self, *args, **options):
        instruments = self._resolve_instruments()
        if not instruments:
            self.stderr.write(
                self.style.ERROR(
                    "Catalog instruments not found — run "
                    "'manage.py loaddata fixtures/initial_catalog.json' first."
                )
            )
            return

        centers = ExamCenter.objects.filter(is_active=True)
        if options.get("center"):
            centers = centers.filter(pk=options["center"])
        centers = list(centers)
        if not centers:
            self.stderr.write(self.style.ERROR("No active centers found."))
            return

        if options.get("clear"):
            self._clear(centers)

        created_total = 0
        for center in centers:
            created = self._seed_center(center, instruments)
            created_total += created
            self.stdout.write(f"  {center.name}: +{created} examiners")

        self.stdout.write(
            self.style.SUCCESS(
                f"\n✅ Seeded {created_total} new examiners across "
                f"{len(centers)} centers (roster size {len(ROSTER)}/center)."
            )
        )

    # ── helpers ───────────────────────────────────────────────────────────

    @staticmethod
    def _resolve_instruments() -> dict[str, Instrument]:
        mapping: dict[str, Instrument] = {}
        for key, (name, style) in SPEC_ALIASES.items():
            inst = Instrument.objects.filter(name=name, style=style).first()
            if inst:
                mapping[key] = inst
        return mapping

    def _clear(self, centers):
        center_ids = [c.pk for c in centers]
        unavail = ExaminerUnavailability.objects.filter(
            examiner__center_id__in=center_ids
        ).delete()[0]
        examiners = Examiner.objects.filter(center_id__in=center_ids).delete()[0]
        self.stdout.write(
            self.style.WARNING(
                f"  Cleared {examiners} examiners and {unavail} leave records."
            )
        )

    @transaction.atomic
    def _seed_center(self, center, instruments) -> int:
        created = 0
        for username, name, phone, max_e, spec_keys, active in ROSTER:
            email = f"{username}.{center.pk}@trinityexam.vn"
            examiner, is_new = Examiner.objects.get_or_create(
                email=email,
                defaults={
                    "center": center,
                    "name": name,
                    "phone": phone,
                    "max_exams_per_day": max_e,
                    "is_active": active,
                },
            )
            if is_new:
                examiner.specializations.set(
                    [instruments[k] for k in spec_keys if k in instruments]
                )
                created += 1
        self._seed_unavailability(center)
        return created

    def _seed_unavailability(self, center):
        """Give the first examiner a short leave starting next week."""
        examiner = Examiner.objects.filter(center=center).order_by("pk").first()
        if examiner is None:
            return
        start = datetime.date.today() + datetime.timedelta(days=7)
        ExaminerUnavailability.objects.get_or_create(
            examiner=examiner,
            date_from=start,
            date_to=start + datetime.timedelta(days=1),
            defaults={"reason": "Nghỉ phép cá nhân"},
        )
