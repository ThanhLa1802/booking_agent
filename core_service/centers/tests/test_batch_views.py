"""
Tests for BatchScheduleView and BatchScheduleConfirmView.
"""
from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest
from django.contrib.auth.models import User
from rest_framework.test import APIClient


# ── helpers ───────────────────────────────────────────────────────────────────

def _make_admin_client(db):
    user = User.objects.create_user("admin1", password="pass")
    from accounts.models import UserProfile, UserRole
    UserProfile.objects.create(user=user, role=UserRole.CENTER_ADMIN)
    from centers.models import ExamCenter
    center = ExamCenter.objects.create(name="Test Center", city="Hanoi", address="123 St", admin_user=user)
    client = APIClient()
    client.force_authenticate(user=user)
    return client, user, center


# ── BatchScheduleView ─────────────────────────────────────────────────────────

@pytest.mark.django_db
@patch("centers.views.solve_schedule_plan")
def test_batch_schedule_returns_202_with_task_id(mock_task):
    """POST /api/centers/schedule/batch/ fires task and returns 202 + task_id."""
    mock_task.delay.return_value = MagicMock(id="test-task-id-123")

    client, user, center = _make_admin_client(None)
    resp = client.post(
        "/api/centers/schedule/batch/",
        {"date_from": "2026-06-01", "date_to": "2026-06-30"},
        format="json",
    )

    assert resp.status_code == 202
    assert resp.json()["task_id"] == "test-task-id-123"
    mock_task.delay.assert_called_once_with(
        center_id=center.pk,
        date_from="2026-06-01",
        date_to="2026-06-30",
        user_id=user.pk,
    )


@pytest.mark.django_db
def test_batch_schedule_rejects_range_over_31_days():
    client, _, _ = _make_admin_client(None)
    resp = client.post(
        "/api/centers/schedule/batch/",
        {"date_from": "2026-06-01", "date_to": "2026-08-31"},
        format="json",
    )
    assert resp.status_code == 400


@pytest.mark.django_db
def test_batch_schedule_requires_center_admin():
    user = User.objects.create_user("student1", password="pass")
    from accounts.models import UserProfile, UserRole
    UserProfile.objects.create(user=user, role=UserRole.STUDENT)
    client = APIClient()
    client.force_authenticate(user=user)

    resp = client.post(
        "/api/centers/schedule/batch/",
        {"date_from": "2026-06-01", "date_to": "2026-06-30"},
        format="json",
    )
    assert resp.status_code == 403


# ── BatchScheduleConfirmView ──────────────────────────────────────────────────

@pytest.mark.django_db
@patch("centers.views._redis")
def test_confirm_bulk_assigns_slots(mock_redis_module):
    """POST confirm reads Redis plan and bulk-assigns in transaction."""
    client, user, center = _make_admin_client(None)

    from catalog.models import Course, Instrument
    from centers.models import Examiner, ExamSlot

    instrument = Instrument.objects.create(name="Piano", style="CLASSICAL_JAZZ")
    course = Course.objects.create(
        instrument=instrument, grade=1, name="Piano G1", duration_minutes=10, fee=100
    )
    import datetime
    slot = ExamSlot.objects.create(
        center=center, course=course,
        exam_date=datetime.date(2026, 6, 1),
        start_time=datetime.time(9, 0),
        capacity=5,
    )
    examiner = Examiner.objects.create(
        center=center, name="Nguyen A", email="a@test.com"
    )

    plan_data = {
        "status": "SUCCESS",
        "task_id": "abc-123",
        "center_id": center.pk,
        "user_id": user.pk,
        "date_from": "2026-06-01",
        "date_to": "2026-06-30",
        "plan": [{"slot_id": slot.pk, "examiner_id": examiner.pk}],
        "unassigned": [],
    }
    mock_rc = MagicMock()
    mock_rc.get.return_value = json.dumps(plan_data)
    mock_redis_module.from_url.return_value = mock_rc

    resp = client.post("/api/centers/schedule/batch/abc-123/confirm/")

    assert resp.status_code == 200
    assert resp.json()["assigned_count"] == 1

    slot.refresh_from_db()
    assert slot.examiner_id == examiner.pk


@pytest.mark.django_db
@patch("centers.views._redis")
def test_confirm_rejects_wrong_user(mock_redis_module):
    """Another user cannot confirm someone else's task."""
    client, user, center = _make_admin_client(None)

    plan_data = {
        "status": "SUCCESS",
        "task_id": "abc-123",
        "center_id": center.pk,
        "user_id": user.pk + 999,   # different user
        "plan": [],
        "unassigned": [],
    }
    mock_rc = MagicMock()
    mock_rc.get.return_value = json.dumps(plan_data)
    mock_redis_module.from_url.return_value = mock_rc

    resp = client.post("/api/centers/schedule/batch/abc-123/confirm/")
    assert resp.status_code == 403


@pytest.mark.django_db
@patch("centers.views._redis")
def test_confirm_returns_404_for_missing_task(mock_redis_module):
    client, _, _ = _make_admin_client(None)
    mock_rc = MagicMock()
    mock_rc.get.return_value = None
    mock_redis_module.from_url.return_value = mock_rc

    resp = client.post("/api/centers/schedule/batch/no-such-task/confirm/")
    assert resp.status_code == 404
