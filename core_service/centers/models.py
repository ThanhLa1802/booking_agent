import datetime

from django.db import models
from django.contrib.auth.models import User


class ExamCenter(models.Model):
    name = models.CharField(max_length=200)
    city = models.CharField(max_length=100)
    address = models.TextField()
    phone = models.CharField(max_length=20, blank=True)
    email = models.EmailField(blank=True)
    admin_user = models.OneToOneField(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="managed_center",
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["city", "name"]

    def __str__(self):
        return f"{self.name} ({self.city})"


class Examiner(models.Model):
    """A music examiner who is assigned to exam slots at a center."""

    center = models.ForeignKey(
        ExamCenter, on_delete=models.CASCADE, related_name="examiners"
    )
    name = models.CharField(max_length=200)
    email = models.EmailField(unique=True)
    phone = models.CharField(max_length=20, blank=True)
    specializations = models.ManyToManyField(
        "catalog.Instrument",
        blank=True,
        related_name="examiners",
        help_text="Instruments/styles this examiner is qualified to assess.",
    )
    max_exams_per_day = models.PositiveSmallIntegerField(
        default=8,
        help_text="Maximum number of exam slots this examiner can be assigned per day.",
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["center", "name"]

    def __str__(self):
        return f"{self.name} ({self.center.name})"

    # ── availability helpers ───────────────────────────────────────────────

    def is_unavailable_on(self, date: datetime.date) -> bool:
        """Return True if the examiner has an unavailability period covering *date*."""
        return self.unavailabilities.filter(
            date_from__lte=date,
            date_to__gte=date,
        ).exists()

    def daily_load(self, date: datetime.date) -> int:
        """Return the number of slots assigned to this examiner on *date*."""
        return self.slots.filter(exam_date=date).count()

    def has_capacity_on(self, date: datetime.date) -> bool:
        """Return True if the examiner can take on another slot on *date*."""
        return self.daily_load(date) < self.max_exams_per_day

    def is_assignable_to_slot(self, slot: "ExamSlot") -> tuple[bool, str]:
        """
        Check whether this examiner can be assigned to *slot*.
        Returns (ok: bool, reason: str).
        """
        if not self.is_active:
            return False, "Examiner is inactive."
        if self.is_unavailable_on(slot.exam_date):
            return False, f"Examiner is unavailable on {slot.exam_date}."
        if not self.has_capacity_on(slot.exam_date):
            return (
                False,
                f"Examiner has reached the daily limit of "
                f"{self.max_exams_per_day} exams on {slot.exam_date}.",
            )
        return True, ""


class ExaminerUnavailability(models.Model):
    """A date range during which an examiner is unavailable (leave, etc.)."""

    examiner = models.ForeignKey(
        Examiner, on_delete=models.CASCADE, related_name="unavailabilities"
    )
    date_from = models.DateField()
    date_to = models.DateField()
    reason = models.CharField(max_length=300, blank=True)

    class Meta:
        ordering = ["examiner", "date_from"]
        verbose_name_plural = "examiner unavailabilities"

    def __str__(self):
        return f"{self.examiner.name}: {self.date_from} – {self.date_to}"


class ExamSlot(models.Model):
    center = models.ForeignKey(
        ExamCenter, on_delete=models.CASCADE, related_name="slots"
    )
    course = models.ForeignKey(
        "catalog.Course", on_delete=models.PROTECT, related_name="slots"
    )
    examiner = models.ForeignKey(
        Examiner,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="slots",
    )
    exam_date = models.DateField()
    start_time = models.TimeField()
    capacity = models.PositiveSmallIntegerField(default=1)
    reserved_count = models.PositiveSmallIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["exam_date", "start_time"]

    def __str__(self):
        return (
            f"{self.course} @ {self.center.name} "
            f"{self.exam_date} {self.start_time}"
        )

    @property
    def available_capacity(self):
        return self.capacity - self.reserved_count

    @property
    def is_available(self):
        return self.is_active and self.available_capacity > 0
