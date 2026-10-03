from accounts.models import UserProfile, UserRole
from django.contrib.auth.models import User
from django.db import transaction
from rest_framework import serializers

from .models import ExamCenter, Examiner, ExaminerUnavailability, ExamSlot


class ExamCenterSerializer(serializers.ModelSerializer):
    class Meta:
        model = ExamCenter
        fields = ("id", "name", "city", "address", "phone", "email")


def _provision_examiner_login(examiner, password):
    """
    Create a login account (role=EXAMINER) for *examiner* and link it back.
    Raises ValidationError if the examiner's email is already used by a user.
    """
    email = examiner.email
    if (
        User.objects.filter(username=email).exists()
        or User.objects.filter(email__iexact=email).exists()
    ):
        raise serializers.ValidationError(
            {"password": "Email này đã được dùng cho một tài khoản khác."}
        )
    user = User.objects.create_user(username=email, email=email, password=password)
    UserProfile.objects.create(user=user, role=UserRole.EXAMINER, phone=examiner.phone)
    examiner.user = user
    examiner.save(update_fields=["user"])
    return user


class ExaminerSerializer(serializers.ModelSerializer):
    specialization_names = serializers.SerializerMethodField(read_only=True)
    # Optional: when provided on create/update, provision/reset a login account.
    password = serializers.CharField(
        write_only=True, required=False, allow_blank=True, min_length=8
    )
    has_login = serializers.SerializerMethodField(read_only=True)

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
            "password",
            "has_login",
        )
        # `center` is set server-side from the admin's own center (see perform_create).
        extra_kwargs = {
            "center": {"read_only": True},
            "specializations": {"required": False},
        }

    def get_specialization_names(self, obj):
        return [str(i) for i in obj.specializations.all()]

    def get_has_login(self, obj):
        return obj.user_id is not None

    @transaction.atomic
    def create(self, validated_data):
        password = validated_data.pop("password", "")
        examiner = super().create(validated_data)
        if password:
            _provision_examiner_login(examiner, password)
        return examiner

    @transaction.atomic
    def update(self, instance, validated_data):
        password = validated_data.pop("password", "")
        old_email = instance.email
        examiner = super().update(instance, validated_data)

        user = examiner.user
        if user is not None and examiner.email != old_email:
            email_taken = (
                User.objects.filter(username=examiner.email).exclude(pk=user.pk).exists()
                or User.objects.filter(email__iexact=examiner.email)
                .exclude(pk=user.pk)
                .exists()
            )
            if email_taken:
                raise serializers.ValidationError(
                    {"email": "Email này đã được dùng cho một tài khoản khác."}
                )
            user.username = examiner.email
            user.email = examiner.email
            user.save(update_fields=["username", "email"])

        if password:
            if user is None:
                _provision_examiner_login(examiner, password)
            else:
                user.set_password(password)
                user.save(update_fields=["password"])
        return examiner


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
