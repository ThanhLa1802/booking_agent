"""
Unit tests for centers.tasks.solve_schedule_plan.

Uses mocks for ORM and solver — no real DB, no real Redis.
"""
from __future__ import annotations

import json
from datetime import date, time
from unittest.mock import MagicMock, call, patch

import pytest


# ── helpers ───────────────────────────────────────────────────────────────────

def _make_slot(id, exam_date="2026-06-01", start_time="09:00", instrument_id=1):
    slot = MagicMock()
    slot.id = id
    slot.exam_date = date.fromisoformat(exam_date)
    slot.start_time = time.fromisoformat(start_time)
    slot.course.instrument_id = instrument_id
    slot.course.__str__ = lambda s: "Piano Grade 3"
    return slot


def _make_examiner(id, name="Nguyen A", max_per_day=8):
    e = MagicMock()
    e.id = id
    e.name = name
    e.max_exams_per_day = max_per_day
    e.specializations.all.return_value = [MagicMock(id=1)]
    e.unavailabilities.all.return_value = []
    return e


# ── tests ─────────────────────────────────────────────────────────────────────

@patch("centers.tasks._get_redis")
@patch("centers.tasks.solve")
@patch("centers.tasks.ExamSlot")
@patch("centers.tasks.Examiner")
def test_task_stores_plan_in_redis_no_db_write(
    mock_Examiner, mock_ExamSlot, mock_solve, mock_get_redis
):
    """Happy path: task stores plan in Redis and does NOT call ExamSlot.save()."""
    slot = _make_slot(id=5)
    examiner = _make_examiner(id=10)

    # ORM query returns
    mock_ExamSlot.objects.filter.return_value.select_related.return_value.order_by.return_value = [slot]
    mock_ExamSlot.objects.filter.return_value.values.return_value.annotate.return_value = []
    mock_Examiner.objects.filter.return_value.prefetch_related.return_value = [examiner]

    mock_solve.return_value = [{"slot_id": 5, "examiner_id": 10}]

    rc = MagicMock()
    mock_get_redis.return_value = rc

    from centers.tasks import solve_schedule_plan
    # Simulate Celery task execution (call underlying function directly)
    solve_schedule_plan.run(
        center_id=1,
        date_from="2026-06-01",
        date_to="2026-06-30",
        user_id=42,
    )

    # Redis setex was called twice: once for PENDING, once for SUCCESS
    assert rc.setex.call_count == 2

    # Second call contains the plan
    last_call_args = rc.setex.call_args_list[-1]
    key = last_call_args[0][0]
    payload = json.loads(last_call_args[0][2])

    assert key.startswith("schedule_task:")
    assert payload["status"] == "SUCCESS"
    assert len(payload["plan"]) == 1
    assert payload["plan"][0]["slot_id"] == 5
    assert payload["plan"][0]["examiner_id"] == 10
    assert payload["unassigned"] == []

    # CRITICAL: no ExamSlot.save() called — plan-only step
    slot.save.assert_not_called()


@patch("centers.tasks._get_redis")
@patch("centers.tasks.ExamSlot")
@patch("centers.tasks.Examiner")
def test_task_no_slots_returns_empty_plan(
    mock_Examiner, mock_ExamSlot, mock_get_redis
):
    """When there are no unassigned slots, task stores empty plan."""
    mock_ExamSlot.objects.filter.return_value.select_related.return_value.order_by.return_value = []
    rc = MagicMock()
    mock_get_redis.return_value = rc

    from centers.tasks import solve_schedule_plan
    solve_schedule_plan.run(
        center_id=1, date_from="2026-06-01", date_to="2026-06-30", user_id=42
    )

    last_payload = json.loads(rc.setex.call_args_list[-1][0][2])
    assert last_payload["status"] == "SUCCESS"
    assert last_payload["plan"] == []
    assert last_payload["unassigned"] == []


@patch("centers.tasks._get_redis")
@patch("centers.tasks.ExamSlot")
@patch("centers.tasks.Examiner")
def test_task_no_examiners_all_unassigned(
    mock_Examiner, mock_ExamSlot, mock_get_redis
):
    """When no examiners available, all slots go into unassigned list."""
    slot = _make_slot(id=7)
    mock_ExamSlot.objects.filter.return_value.select_related.return_value.order_by.return_value = [slot]
    mock_Examiner.objects.filter.return_value.prefetch_related.return_value = []
    rc = MagicMock()
    mock_get_redis.return_value = rc

    from centers.tasks import solve_schedule_plan
    solve_schedule_plan.run(
        center_id=1, date_from="2026-06-01", date_to="2026-06-30", user_id=42
    )

    last_payload = json.loads(rc.setex.call_args_list[-1][0][2])
    assert last_payload["status"] == "SUCCESS"
    assert last_payload["plan"] == []
    assert len(last_payload["unassigned"]) == 1
    assert last_payload["unassigned"][0]["slot_id"] == 7


@patch("centers.tasks._get_redis")
@patch("centers.tasks.ExamSlot")
@patch("centers.tasks.Examiner")
def test_task_on_error_stores_failure(
    mock_Examiner, mock_ExamSlot, mock_get_redis
):
    """When the ORM raises, task stores FAILURE in Redis and re-raises."""
    mock_ExamSlot.objects.filter.side_effect = RuntimeError("DB down")
    rc = MagicMock()
    mock_get_redis.return_value = rc

    from centers.tasks import solve_schedule_plan
    with pytest.raises(RuntimeError):
        solve_schedule_plan.run(
            center_id=1, date_from="2026-06-01", date_to="2026-06-30", user_id=42
        )

    # Last Redis write should be FAILURE
    last_payload = json.loads(rc.setex.call_args_list[-1][0][2])
    assert last_payload["status"] == "FAILURE"
    assert "DB down" in last_payload["error"]
