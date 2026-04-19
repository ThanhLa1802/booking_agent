import pytest
from catalog.models import Instrument, Course, StyleChoice


@pytest.mark.django_db
class TestCatalogModels:
    def test_instrument_str(self):
        instrument = Instrument(name="Piano", style=StyleChoice.CLASSICAL_JAZZ)
        assert str(instrument) == "Piano (Classical & Jazz)"

    def test_course_str(self):
        instrument = Instrument.objects.create(
            name="Violin", style=StyleChoice.CLASSICAL_JAZZ
        )
        course = Course.objects.create(
            instrument=instrument,
            grade=3,
            name="Violin Grade 3",
            duration_minutes=15,
            fee=900000,
        )
        assert str(course) == "Violin Grade 3"

    def test_unique_instrument_grade(self):
        from django.db import IntegrityError

        instrument = Instrument.objects.create(
            name="Guitar", style=StyleChoice.CLASSICAL_JAZZ
        )
        Course.objects.create(
            instrument=instrument,
            grade=1,
            name="Guitar Grade 1",
            duration_minutes=10,
            fee=800000,
        )
        with pytest.raises(IntegrityError):
            Course.objects.create(
                instrument=instrument,
                grade=1,
                name="Duplicate Guitar Grade 1",
                duration_minutes=10,
                fee=800000,
            )
