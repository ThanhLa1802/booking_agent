"""
Tests for examiner login provisioning (CENTER_ADMIN creates an Examiner and
optionally a linked EXAMINER user account that can log in to view their schedule).
"""
from __future__ import annotations

import pytest
from django.contrib.auth.models import User
from rest_framework.test import APIClient


def _make_admin_client():
    from accounts.models import UserProfile, UserRole

    from centers.models import ExamCenter

    user = User.objects.create_user("admin1", password="pass")
    UserProfile.objects.create(user=user, role=UserRole.CENTER_ADMIN)
    ExamCenter.objects.create(
        name="Test Center", city="Hanoi", address="123 St", admin_user=user
    )
    client = APIClient()
    client.force_authenticate(user=user)
    return client


@pytest.mark.django_db
def test_create_examiner_with_password_provisions_login():
    from centers.models import Examiner

    client = _make_admin_client()
    resp = client.post(
        "/api/centers/examiners/",
        {
            "name": "Giao Vien A",
            "email": "gv.a@example.com",
            "phone": "0900000001",
            "password": "strongpass123",
        },
        format="json",
    )
    assert resp.status_code == 201, resp.content
    assert resp.json()["has_login"] is True

    examiner = Examiner.objects.get(email="gv.a@example.com")
    assert examiner.user is not None
    assert examiner.user.username == "gv.a@example.com"
    assert examiner.user.profile.role == "EXAMINER"
    assert examiner.user.check_password("strongpass123")


@pytest.mark.django_db
def test_create_examiner_without_password_has_no_login():
    from centers.models import Examiner

    client = _make_admin_client()
    resp = client.post(
        "/api/centers/examiners/",
        {"name": "Giao Vien B", "email": "gv.b@example.com"},
        format="json",
    )
    assert resp.status_code == 201, resp.content
    assert resp.json()["has_login"] is False
    assert Examiner.objects.get(email="gv.b@example.com").user is None


@pytest.mark.django_db
def test_create_examiner_with_duplicate_user_email_rejected():
    from centers.models import Examiner

    User.objects.create_user(
        username="gv.c@example.com", email="gv.c@example.com", password="x"
    )
    client = _make_admin_client()
    resp = client.post(
        "/api/centers/examiners/",
        {
            "name": "Giao Vien C",
            "email": "gv.c@example.com",
            "password": "strongpass123",
        },
        format="json",
    )
    assert resp.status_code == 400
    assert not Examiner.objects.filter(email="gv.c@example.com").exists()


@pytest.mark.django_db
def test_update_resets_password():
    from centers.models import Examiner

    client = _make_admin_client()
    resp = client.post(
        "/api/centers/examiners/",
        {
            "name": "Giao Vien D",
            "email": "gv.d@example.com",
            "password": "strongpass123",
        },
        format="json",
    )
    examiner_id = resp.json()["id"]
    user = Examiner.objects.get(pk=examiner_id).user

    resp2 = client.patch(
        f"/api/centers/examiners/{examiner_id}/",
        {"password": "newstrongpass456"},
        format="json",
    )
    assert resp2.status_code == 200, resp2.content

    user.refresh_from_db()
    assert user.check_password("newstrongpass456")
    assert not user.check_password("strongpass123")
