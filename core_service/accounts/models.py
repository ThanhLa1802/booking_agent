from django.db import models
from django.contrib.auth.models import User


class UserRole(models.TextChoices):
    STUDENT = "STUDENT", "Student"
    PARENT = "PARENT", "Parent"
    CENTER_ADMIN = "CENTER_ADMIN", "Center Admin"


class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="profile")
    role = models.CharField(max_length=20, choices=UserRole.choices, default=UserRole.STUDENT)
    phone = models.CharField(max_length=20, blank=True)
    date_of_birth = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.username} ({self.get_role_display()})"
