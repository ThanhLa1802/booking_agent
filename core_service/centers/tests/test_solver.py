"""
Unit tests for centers.solver — OR-Tools CP-SAT examiner assignment.

No Django DB required; all inputs are plain dataclasses.
"""
from __future__ import annotations

import pytest
from centers.solver import ExaminerData, SlotData, solve


# ── helpers ───────────────────────────────────────────────────────────────────

def _slot(id, date="2026-06-01", time="09:00", instrument_id=1):
    return SlotData(id=id, exam_date=date, start_time=time, instrument_id=instrument_id)


def _examiner(id, specs=(1,), max_per_day=8, loads=None, unavail=None):
    return ExaminerData(
        id=id,
        max_exams_per_day=max_per_day,
        specialization_ids=set(specs),
        existing_load_by_date=loads or {},
        unavailable_dates=unavail or set(),
    )


# ── 1. happy path ─────────────────────────────────────────────────────────────

def test_all_slots_assigned():
    slots = [_slot(1), _slot(2, time="10:00"), _slot(3, time="11:00")]
    examiners = [_examiner(10)]
    plan = solve(slots, examiners)
    assert len(plan) == 3
    assigned_slots = {a["slot_id"] for a in plan}
    assert assigned_slots == {1, 2, 3}


# ── 2. load balancing ─────────────────────────────────────────────────────────

def test_balanced_load_across_examiners():
    """Four slots, two examiners — each should get exactly two."""
    slots = [
        _slot(1, time="09:00"),
        _slot(2, time="10:00"),
        _slot(3, time="11:00"),
        _slot(4, time="12:00"),
    ]
    examiners = [_examiner(10), _examiner(11)]
    plan = solve(slots, examiners)
    assert len(plan) == 4
    counts = {}
    for a in plan:
        counts[a["examiner_id"]] = counts.get(a["examiner_id"], 0) + 1
    assert counts[10] == 2
    assert counts[11] == 2


# ── 3. infeasible — wrong specialisation ─────────────────────────────────────

def test_no_eligible_examiner_returns_empty():
    slots = [_slot(1, instrument_id=99)]   # instrument 99 — no examiner has it
    examiners = [_examiner(10, specs=(1, 2))]
    plan = solve(slots, examiners)
    assert plan == []


# ── 4. leave constraint ───────────────────────────────────────────────────────

def test_examiner_on_leave_not_assigned():
    slots = [_slot(1, date="2026-06-05")]
    examiners = [_examiner(10, unavail={"2026-06-05"})]
    plan = solve(slots, examiners)
    assert plan == []


# ── 5. max_exams_per_day respected ───────────────────────────────────────────

def test_max_exams_per_day_not_exceeded():
    """Examiner already has 2 slots on the date; max is 3 → can take 1 more."""
    slots = [
        _slot(1, time="09:00"),
        _slot(2, time="10:00"),  # only one of these two should be assigned
    ]
    examiners = [_examiner(10, max_per_day=3, loads={"2026-06-01": 2})]
    plan = solve(slots, examiners)
    # Only 1 new slot can be taken (3 - 2 = 1 remaining cap)
    assert len(plan) == 1


def test_examiner_at_full_capacity_not_assigned():
    slots = [_slot(1)]
    examiners = [_examiner(10, max_per_day=3, loads={"2026-06-01": 3})]
    plan = solve(slots, examiners)
    assert plan == []


# ── 6. no time overlap ────────────────────────────────────────────────────────

def test_no_time_overlap_same_examiner():
    """Two slots at the same date+time — one examiner cannot cover both."""
    slots = [
        _slot(1, date="2026-06-01", time="09:00"),
        _slot(2, date="2026-06-01", time="09:00"),  # same time!
    ]
    examiners = [_examiner(10)]
    plan = solve(slots, examiners)
    # At most one can be assigned
    assert len(plan) <= 1


def test_two_examiners_cover_same_time_slots():
    """Two slots at the same time, two examiners — both can be covered."""
    slots = [
        _slot(1, date="2026-06-01", time="09:00"),
        _slot(2, date="2026-06-01", time="09:00"),
    ]
    examiners = [_examiner(10), _examiner(11)]
    plan = solve(slots, examiners)
    assert len(plan) == 2


# ── 7. empty inputs ───────────────────────────────────────────────────────────

def test_empty_slots_returns_empty():
    assert solve([], [_examiner(10)]) == []


def test_empty_examiners_returns_empty():
    assert solve([_slot(1)], []) == []


# ── 8. multi-day scenario ─────────────────────────────────────────────────────

def test_multi_day_load_cap():
    """Examiner has cap 2/day across two different days."""
    slots = [
        _slot(1, date="2026-06-01", time="09:00"),
        _slot(2, date="2026-06-01", time="10:00"),
        _slot(3, date="2026-06-01", time="11:00"),   # exceeds cap on day 1
        _slot(4, date="2026-06-02", time="09:00"),
        _slot(5, date="2026-06-02", time="10:00"),
        _slot(6, date="2026-06-02", time="11:00"),   # exceeds cap on day 2
    ]
    examiners = [_examiner(10, max_per_day=2)]
    plan = solve(slots, examiners)
    # Max 2 per day → at most 4 total across 2 days
    assert len(plan) <= 4
    # Check per-day counts
    day1 = [a for a in plan if slots[[s.id for s in slots].index(a["slot_id"])].exam_date == "2026-06-01"]
    day2 = [a for a in plan if slots[[s.id for s in slots].index(a["slot_id"])].exam_date == "2026-06-02"]
    assert len(day1) <= 2
    assert len(day2) <= 2
