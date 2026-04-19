from django.contrib.auth.models import User
from django.db import transaction
from rest_framework import serializers
from .models import UserProfile, UserRole


class RegisterSerializer(serializers.Serializer):
    username = serializers.CharField(max_length=150)
    email = serializers.EmailField()
    password = serializers.CharField(min_length=8, write_only=True)
    role = serializers.ChoiceField(
        choices=[UserRole.STUDENT, UserRole.PARENT],
        default=UserRole.STUDENT,
    )
    phone = serializers.CharField(max_length=20, required=False, allow_blank=True)
    date_of_birth = serializers.DateField(required=False, allow_null=True)

    def validate_username(self, value):
        if User.objects.filter(username=value).exists():
            raise serializers.ValidationError("Username already taken.")
        return value

    def validate_email(self, value):
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError("Email already registered.")
        return value

    @transaction.atomic
    def create(self, validated_data):
        role = validated_data.pop("role", UserRole.STUDENT)
        phone = validated_data.pop("phone", "")
        date_of_birth = validated_data.pop("date_of_birth", None)
        user = User.objects.create_user(
            username=validated_data["username"],
            email=validated_data["email"],
            password=validated_data["password"],
        )
        UserProfile.objects.create(
            user=user,
            role=role,
            phone=phone,
            date_of_birth=date_of_birth,
        )
        return user


class UserProfileSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source="user.username", read_only=True)
    email = serializers.EmailField(source="user.email", read_only=True)
    role_display = serializers.CharField(source="get_role_display", read_only=True)

    class Meta:
        model = UserProfile
        fields = ("username", "email", "role", "role_display", "phone", "date_of_birth")
