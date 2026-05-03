"""
Celery tasks for batch exam schedule planning.

solve_schedule_plan:
  - Fetches unassigned slots + examiners from DB via Django ORM.
  - Calls OR-Tools CP-SAT solver (plan only — does NOT write to DB).
  - Stores the plan in Redis under key  schedule_task:{task_id}  (TTL 2 h).
  - A separate HTTP call (BatchScheduleConfirmView) must be made before
    any DB writes occur, after the admin reviews and confirms the plan.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta, timezone

from celery import shared_task
from django.conf import settings
from django.db.models import Count

from centers.models import ExamSlot, Examiner
from centers.solver import ExaminerData, SlotData, solve

logger = logging.getLogger(__name__)

TASK_TTL = 7_200   # seconds — 2 hours


# ── Redis helper ──────────────────────────────────────────────────────────────

def _get_redis():
    import redis as _redis  # sync redis-py (already in requirements)
    return _redis.from_url(settings.REDIS_URL, decode_responses=True)


def _store(redis_client, key: str, payload: dict) -> None:
    redis_client.setex(key, TASK_TTL, json.dumps(payload))


# ── task ──────────────────────────────────────────────────────────────────────

@shared_task(bind=True, name="centers.tasks.solve_schedule_plan")
def solve_schedule_plan(
    self,
    center_id: int,
    date_from: str,
    date_to: str,
    user_id: int,
) -> None:
    """
    Background task: generate an OR-Tools schedule plan (read-only).

    Args:
        center_id: The exam center to schedule for.
        date_from:  Inclusive start date ("YYYY-MM-DD").
        date_to:    Inclusive end date ("YYYY-MM-DD").
        user_id:    ID of the CENTER_ADMIN who triggered the task.
    """
    task_id = self.request.id
    redis_key = f"schedule_task:{task_id}"
    rc = _get_redis()

    # Mark as in-progress immediately so the caller can poll
    _store(rc, redis_key, {
        "status": "PENDING",
        "task_id": task_id,
        "center_id": center_id,
        "user_id": user_id,
        "date_from": date_from,
        "date_to": date_to,
    })

    try:
        # ── 1. fetch unassigned slots ─────────────────────────────────────────
        slots_qs = (
            ExamSlot.objects
            .filter(
                center_id=center_id,
                is_active=True,
                examiner__isnull=True,
                exam_date__gte=date_from,
                exam_date__lte=date_to,
            )
            .select_related("course__instrument")
            .order_by("exam_date", "start_time")
        )
        slots_list = list(slots_qs)

        if not slots_list:
            _store(rc, redis_key, {
                "status": "SUCCESS",
                "task_id": task_id,
                "center_id": center_id,
                "user_id": user_id,
                "date_from": date_from,
                "date_to": date_to,
                "plan": [],
                "unassigned": [],
                "created_at": datetime.now(timezone.utc).isoformat(),
            })
            return

        slot_data = [
            SlotData(
                id=s.id,
                exam_date=s.exam_date.isoformat(),
                start_time=str(s.start_time)[:5],   # "HH:MM"
                instrument_id=s.course.instrument_id,
            )
            for s in slots_list
        ]

        # ── 2. fetch active examiners ─────────────────────────────────────────
        examiners_qs = list(
            Examiner.objects
            .filter(center_id=center_id, is_active=True)
            .prefetch_related("specializations", "unavailabilities")
        )

        if not examiners_qs:
            unassigned = [
                {
                    "slot_id": s.id,
                    "exam_date": s.exam_date.isoformat(),
                    "start_time": str(s.start_time)[:5],
                    "course_name": str(s.course),
                    "reason": "No active examiners at this center",
                }
                for s in slots_list
            ]
            _store(rc, redis_key, {
                "status": "SUCCESS",
                "task_id": task_id,
                "center_id": center_id,
                "user_id": user_id,
                "date_from": date_from,
                "date_to": date_to,
                "plan": [],
                "unassigned": unassigned,
                "created_at": datetime.now(timezone.utc).isoformat(),
            })
            return

        # Batch-load existing slot counts for the date range (avoid N+1)
        existing_load_rows = (
            ExamSlot.objects
            .filter(
                examiner__center_id=center_id,
                examiner__isnull=False,
                exam_date__gte=date_from,
                exam_date__lte=date_to,
            )
            .values("examiner_id", "exam_date")
            .annotate(cnt=Count("id"))
        )
        # load_map[(examiner_id, "YYYY-MM-DD")] = count
        load_map: dict[tuple, int] = {
            (row["examiner_id"], str(row["exam_date"])): row["cnt"]
            for row in existing_load_rows
        }

        examiner_name_map: dict[int, str] = {}
        examiner_data: list[ExaminerData] = []

        for e in examiners_qs:
            examiner_name_map[e.id] = e.name

            # Expand unavailability periods into individual date strings
            unavail_dates: set[str] = set()
            for u in e.unavailabilities.all():
                cur = u.date_from
                while cur <= u.date_to:
                    unavail_dates.add(cur.isoformat())
                    cur += timedelta(days=1)

            load_by_date = {
                date_str: load_map.get((e.id, date_str), 0)
                for date_str in {s.exam_date.isoformat() for s in slots_list}
            }

            examiner_data.append(ExaminerData(
                id=e.id,
                max_exams_per_day=e.max_exams_per_day,
                specialization_ids={i.id for i in e.specializations.all()},
                existing_load_by_date=load_by_date,
                unavailable_dates=unavail_dates,
            ))

        # ── 3. solve ──────────────────────────────────────────────────────────
        assignments = solve(slot_data, examiner_data)
        assigned_slot_ids = {a["slot_id"] for a in assignments}

        slot_lookup = {s.id: s for s in slots_list}
        plan = [
            {
                "slot_id": a["slot_id"],
                "examiner_id": a["examiner_id"],
                "examiner_name": examiner_name_map.get(a["examiner_id"], str(a["examiner_id"])),
                "exam_date": slot_lookup[a["slot_id"]].exam_date.isoformat(),
                "start_time": str(slot_lookup[a["slot_id"]].start_time)[:5],
                "course_name": str(slot_lookup[a["slot_id"]].course),
            }
            for a in assignments
        ]

        unassigned = [
            {
                "slot_id": s.id,
                "exam_date": s.exam_date.isoformat(),
                "start_time": str(s.start_time)[:5],
                "course_name": str(s.course),
                "reason": "No eligible examiner available",
            }
            for s in slots_list
            if s.id not in assigned_slot_ids
        ]

        # ── 4. store plan in Redis (NO DB write) ──────────────────────────────
        _store(rc, redis_key, {
            "status": "SUCCESS",
            "task_id": task_id,
            "center_id": center_id,
            "user_id": user_id,
            "date_from": date_from,
            "date_to": date_to,
            "plan": plan,
            "unassigned": unassigned,
            "created_at": datetime.now(timezone.utc).isoformat(),
        })

        logger.info(
            "solve_schedule_plan[%s]: center=%s assigned=%d unassigned=%d",
            task_id, center_id, len(plan), len(unassigned),
        )

    except Exception as exc:
        logger.exception("solve_schedule_plan[%s] error: %s", task_id, exc)
        _store(rc, redis_key, {
            "status": "FAILURE",
            "task_id": task_id,
            "center_id": center_id,
            "user_id": user_id,
            "error": str(exc),
            "created_at": datetime.now(timezone.utc).isoformat(),
        })
        raise
