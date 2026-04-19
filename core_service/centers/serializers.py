from rest_framework import serializers
from .models import ExamCenter, ExamSlot


class ExamCenterSerializer(serializers.ModelSerializer):
    class Meta:
        model = ExamCenter
        fields = ("id", "name", "city", "address", "phone", "email")


class ExamSlotSerializer(serializers.ModelSerializer):
    center_name = serializers.CharField(source="center.name", read_only=True)
    center_city = serializers.CharField(source="center.city", read_only=True)
    course_name = serializers.SerializerMethodField()
    available_capacity = serializers.IntegerField(read_only=True)

    class Meta:
        model = ExamSlot
        fields = (
            "id",
            "center",
            "center_name",
            "center_city",
            "course",
            "course_name",
            "exam_date",
            "start_time",
            "capacity",
            "available_capacity",
        )

    def get_course_name(self, obj):
        return str(obj.course)
