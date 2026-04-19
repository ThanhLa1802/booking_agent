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


class ExamSlot(models.Model):
    center = models.ForeignKey(
        ExamCenter, on_delete=models.CASCADE, related_name="slots"
    )
    course = models.ForeignKey(
        "catalog.Course", on_delete=models.PROTECT, related_name="slots"
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
