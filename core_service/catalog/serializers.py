from rest_framework import serializers
from .models import Instrument, Course


class InstrumentSerializer(serializers.ModelSerializer):
    style_display = serializers.CharField(source="get_style_display", read_only=True)

    class Meta:
        model = Instrument
        fields = ("id", "name", "style", "style_display")


class CourseSerializer(serializers.ModelSerializer):
    instrument_name = serializers.CharField(source="instrument.name", read_only=True)
    style = serializers.CharField(source="instrument.style", read_only=True)
    style_display = serializers.CharField(
        source="instrument.get_style_display", read_only=True
    )

    class Meta:
        model = Course
        fields = (
            "id",
            "instrument",
            "instrument_name",
            "style",
            "style_display",
            "grade",
            "name",
            "description",
            "duration_minutes",
            "fee",
        )
