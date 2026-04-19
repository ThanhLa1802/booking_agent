from django.db import models


class StyleChoice(models.TextChoices):
    CLASSICAL_JAZZ = "CLASSICAL_JAZZ", "Classical & Jazz"
    ROCK_POP = "ROCK_POP", "Rock & Pop"
    THEORY = "THEORY", "Theory of Music"


class Instrument(models.Model):
    name = models.CharField(max_length=100, unique=True)
    style = models.CharField(max_length=20, choices=StyleChoice.choices)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["style", "name"]

    def __str__(self):
        return f"{self.name} ({self.get_style_display()})"


class Course(models.Model):
    instrument = models.ForeignKey(
        Instrument, on_delete=models.PROTECT, related_name="courses"
    )
    grade = models.PositiveSmallIntegerField()  # 1–8
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    duration_minutes = models.PositiveSmallIntegerField()
    fee = models.DecimalField(max_digits=10, decimal_places=0)  # VNĐ
    is_active = models.BooleanField(default=True)

    class Meta:
        unique_together = ("instrument", "grade")
        ordering = ["instrument__style", "instrument__name", "grade"]

    def __str__(self):
        return f"{self.instrument.name} Grade {self.grade}"
