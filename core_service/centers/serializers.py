from rest_framework import serializers
from .models import ExamCenter, ExamSlot, Examiner, ExaminerUnavailability


class ExamCenterSerializer(serializers.ModelSerializer):
    class Meta:
        model = ExamCenter
        fields = ("id", "name", "city", "address", "phone", "email")


class ExaminerSerializer(serializers.ModelSerializer):
    specialization_names = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = Examiner
        fields = (
            "id",
            "center",
            "name",
            "email",
            "phone",
            "specializations",
            "specialization_names",
            "max_exams_per_day",
            "is_active",
        )
        extra_kwargs = {"specializations": {"required": False}}

    def get_specialization_names(self, obj):
        return [str(i) for i in obj.specializations.all()]


class ExaminerUnavailabilitySerializer(serializers.ModelSerializer):
    class Meta:
        model = ExaminerUnavailability
        fields = ("id", "examiner", "date_from", "date_to", "reason")

    def validate(self, data):
        if data["date_from"] > data["date_to"]:
            raise serializers.ValidationError(
                "date_from must be on or before date_to."
            )
        return data


class ExamSlotSerializer(serializers.ModelSerializer):
    center_name = serializers.CharField(source="center.name", read_only=True)
    center_city = serializers.CharField(source="center.city", read_only=True)
    course_name = serializers.SerializerMethodField()
    available_capacity = serializers.IntegerField(read_only=True)
    examiner_name = serializers.SerializerMethodField()

    class Meta:
        model = ExamSlot
        fields = (
            "id",
            "center",
            "center_name",
            "center_city",
            "course",
            "course_name",
            "examiner",
            "examiner_name",
            "exam_date",
            "start_time",
            "capacity",
            "available_capacity",
        )

    def get_course_name(self, obj):
        return str(obj.course)

    def get_examiner_name(self, obj):
        return obj.examiner.name if obj.examiner_id else None


class AssignExaminerSerializer(serializers.Serializer):
    examiner_id = serializers.IntegerField()

    def validate_examiner_id(self, value):
        try:
            Examiner.objects.get(pk=value, is_active=True)
        except Examiner.DoesNotExist:
            raise serializers.ValidationError("Examiner not found or inactive.")
        return value
