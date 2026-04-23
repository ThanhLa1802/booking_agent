from django.contrib.auth import authenticate
from django.contrib.auth.models import User
from django.db import transaction
from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
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


class EmailTokenObtainPairSerializer(TokenObtainPairSerializer):
    """Accept email + password instead of username + password."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["email"] = serializers.EmailField()
        del self.fields[self.username_field]

    def validate(self, attrs):
        email = attrs.pop("email")
        try:
            user_obj = User.objects.get(email=email)
        except User.DoesNotExist:
            raise serializers.ValidationError({"email": "Không tìm thấy tài khoản với email này."})
        attrs[self.username_field] = user_obj.username
        data = super().validate(attrs)
        # Include basic user info so frontend can hydrate the store
        data["user"] = {
            "id": user_obj.id,
            "username": user_obj.username,
            "email": user_obj.email,
            "role": getattr(getattr(user_obj, "profile", None), "role", "STUDENT"),
        }
        return data

    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        token["username"] = user.username
        token["email"] = user.email
        return token


class UserProfileSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source="user.username", read_only=True)
    email = serializers.EmailField(source="user.email", read_only=True)
    role_display = serializers.CharField(source="get_role_display", read_only=True)

    class Meta:
        model = UserProfile
        fields = ("username", "email", "role", "role_display", "phone", "date_of_birth")
