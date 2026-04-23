import pytest
from unittest.mock import patch, MagicMock
from django.contrib.auth.models import User


@pytest.mark.django_db
class TestRegisterSerializer:
    def test_valid_registration(self):
        from accounts.serializers import RegisterSerializer

        data = {
            "username": "student1",
            "email": "student1@example.com",
            "password": "securepass123",
            "role": "STUDENT",
            "phone": "0901234567",
        }
        serializer = RegisterSerializer(data=data)
        assert serializer.is_valid(), serializer.errors
        user = serializer.save()
        assert user.pk is not None
        assert user.profile.role == "STUDENT"
        assert user.profile.phone == "0901234567"

    def test_duplicate_username_rejected(self):
        from accounts.serializers import RegisterSerializer

        User.objects.create_user(username="taken", email="taken@x.com", password="x")
        data = {
            "username": "taken",
            "email": "new@example.com",
            "password": "securepass123",
        }
        serializer = RegisterSerializer(data=data)
        assert not serializer.is_valid()
        assert "username" in serializer.errors

    def test_duplicate_email_rejected(self):
        from accounts.serializers import RegisterSerializer

        User.objects.create_user(username="user2", email="dup@example.com", password="x")
        data = {
            "username": "newuser",
            "email": "dup@example.com",
            "password": "securepass123",
        }
        serializer = RegisterSerializer(data=data)
        assert not serializer.is_valid()
        assert "email" in serializer.errors

    def test_short_password_rejected(self):
        from accounts.serializers import RegisterSerializer

        data = {
            "username": "newuser2",
            "email": "newuser2@example.com",
            "password": "short",
        }
        serializer = RegisterSerializer(data=data)
        assert not serializer.is_valid()
        assert "password" in serializer.errors
