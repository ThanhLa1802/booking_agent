"""
OR-Tools CP-SAT solver for batch examiner assignment.

Pure Python — no Django ORM, no async.  Accepts plain dataclasses so it can
run inside a Celery worker, a unit test, or any other context.

Usage:
    from centers.solver import SlotData, ExaminerData, solve

    plan = solve(slot_list, examiner_list)
    # → [{"slot_id": 5, "examiner_id": 2}, ...]
"""
from __future__ import annotations

import logging
from collections import defaultdict
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


# ── data classes ──────────────────────────────────────────────────────────────


@dataclass
class SlotData:
    """Plain-Python representation of one unassigned exam slot."""

    id: int
    exam_date: str          # "YYYY-MM-DD"
    start_time: str         # "HH:MM"
    instrument_id: int


@dataclass
class ExaminerData:
    """Plain-Python representation of one examiner and their constraints."""

    id: int
    max_exams_per_day: int
    specialization_ids: set[int]
    # date_str → number of slots already assigned on that date (before this batch)
    existing_load_by_date: dict[str, int] = field(default_factory=dict)
    # "YYYY-MM-DD" strings on which this examiner is on leave
    unavailable_dates: set[str] = field(default_factory=set)


# ── solver ────────────────────────────────────────────────────────────────────


def solve(slots: list[SlotData], examiners: list[ExaminerData]) -> list[dict]:
    """
    Assign examiners to unassigned exam slots using OR-Tools CP-SAT.

    Constraints:
      - Each slot gets at most one examiner (exactly one when feasible).
      - Examiner must hold the required instrument specialization.
      - Examiner must not be on leave on the slot date.
      - Examiner cannot exceed ``max_exams_per_day`` (existing + new).
      - Two slots at the same (date, time) cannot share the same examiner.

    Objective: maximise total assigned slots first, then minimise
    ``max_load − min_load`` across examiners (balance).

    Returns:
        List of ``{"slot_id": int, "examiner_id": int}`` dicts.
        Returns ``[]`` when infeasible or if ortools is not installed.
    """
    if not slots or not examiners:
        return []

    try:
        from ortools.sat.python import cp_model  # type: ignore[import]
    except ImportError:  # pragma: no cover
        logger.error("ortools is not installed — cannot solve schedule")
        return []

    model = cp_model.CpModel()
    n_slots = len(slots)
    n_examiners = len(examiners)

    def _eligible(s: SlotData, e: ExaminerData) -> bool:
        return (
            s.instrument_id in e.specialization_ids
            and s.exam_date not in e.unavailable_dates
        )

    # ── decision variables ────────────────────────────────────────────────────
    # x[i, j] = 1  iff  slot i is assigned to examiner j
    x: dict[tuple[int, int], object] = {}
    for i, slot in enumerate(slots):
        for j, examiner in enumerate(examiners):
            if _eligible(slot, examiner):
                x[i, j] = model.new_bool_var(f"x_{i}_{j}")

    if not x:
        logger.warning("solve: no eligible (slot, examiner) pair found")
        return []

    # ── constraint 1: each slot → at most one examiner ────────────────────────
    for i in range(n_slots):
        eligible_vars = [x[i, j] for j in range(n_examiners) if (i, j) in x]
        if eligible_vars:
            model.add(sum(eligible_vars) <= 1)

    # ── constraint 2: max_exams_per_day per examiner per date ─────────────────
    unique_dates = sorted({s.exam_date for s in slots})
    for j, examiner in enumerate(examiners):
        for date_str in unique_dates:
            slots_on_date = [i for i, s in enumerate(slots) if s.exam_date == date_str]
            eligible_on_date = [x[i, j] for i in slots_on_date if (i, j) in x]
            if not eligible_on_date:
                continue
            existing = examiner.existing_load_by_date.get(date_str, 0)
            remaining = examiner.max_exams_per_day - existing
            if remaining <= 0:
                for var in eligible_on_date:
                    model.add(var == 0)
            else:
                model.add(sum(eligible_on_date) <= remaining)

    # ── constraint 3: no time-overlap for same examiner ───────────────────────
    time_groups: dict[tuple[str, str], list[int]] = defaultdict(list)
    for i, s in enumerate(slots):
        time_groups[(s.exam_date, s.start_time)].append(i)

    for (_, _), slot_indices in time_groups.items():
        if len(slot_indices) < 2:
            continue
        for j in range(n_examiners):
            same_time_vars = [x[i, j] for i in slot_indices if (i, j) in x]
            if len(same_time_vars) > 1:
                model.add(sum(same_time_vars) <= 1)

    # ── objective: maximise assigned + balance ────────────────────────────────
    all_vars = list(x.values())

    load_vars = []
    for j in range(n_examiners):
        ev = [x[i, j] for i in range(n_slots) if (i, j) in x]
        lv = model.new_int_var(0, n_slots, f"load_{j}")
        model.add(lv == (sum(ev) if ev else 0))
        load_vars.append(lv)

    max_load = model.new_int_var(0, n_slots, "max_load")
    min_load = model.new_int_var(0, n_slots, "min_load")
    model.add_max_equality(max_load, load_vars)
    model.add_min_equality(min_load, load_vars)

    # 100× weight on coverage; 1× penalty on imbalance
    model.maximize(100 * sum(all_vars) - (max_load - min_load))

    # ── solve ─────────────────────────────────────────────────────────────────
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = 10.0
    solver.parameters.num_search_workers = 1   # deterministic

    solve_status = solver.solve(model)

    if solve_status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        logger.warning(
            "OR-Tools: no solution (status=%s)", solver.status_name(solve_status)
        )
        return []

    return [
        {"slot_id": slots[i].id, "examiner_id": examiners[j].id}
        for (i, j), var in x.items()
        if solver.value(var) == 1
    ]
