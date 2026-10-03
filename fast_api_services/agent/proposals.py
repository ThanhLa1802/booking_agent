"""
Map a stored scheduling proposal to the concrete write action it implies.

Both the router (to pre-authorize the action on the confirmation turn) and
``execute_node`` (to invoke it) go through this single function, so the
``(tool, args)`` pair — and therefore its action hash — is guaranteed to match.
"""
from __future__ import annotations

import re
from typing import Optional

_SLOT_RE = re.compile(r"slot\s*[#:]?\s*(\d+)", re.IGNORECASE)
_EXAMINER_RE = re.compile(r"(?:giám\s*khảo|examiner)\s*[#:]?\s*(\d+)", re.IGNORECASE)
_BOOKING_RE = re.compile(r"booking\s*[#:]?\s*(\d+)", re.IGNORECASE)


def proposal_to_action(proposal: Optional[dict]) -> Optional[tuple[str, dict]]:
    """Return ``(tool_name, args)`` for a write proposal, or None if undetermined."""
    if not proposal:
        return None

    task_type = proposal.get("task_type")
    messages_text = " ".join(proposal.get("conversation_messages") or [])

    if task_type == "assign_examiner":
        slot_id = proposal.get("slot_id")
        examiner_id = proposal.get("examiner_id")
        if not slot_id:
            m = _SLOT_RE.search(messages_text)
            slot_id = int(m.group(1)) if m else None
        if not examiner_id:
            m = _EXAMINER_RE.search(messages_text)
            examiner_id = int(m.group(1)) if m else None
        if slot_id and examiner_id:
            return "assign_examiner_to_slot", {
                "slot_id": slot_id,
                "examiner_id": examiner_id,
            }
        return None

    if task_type == "reschedule":
        booking = _BOOKING_RE.search(messages_text)
        slot = _SLOT_RE.search(messages_text)
        if booking and slot:
            return "reschedule_booking", {
                "booking_id": int(booking.group(1)),
                "new_slot_id": int(slot.group(1)),
                "reason": "",
            }
        return None

    if task_type == "batch_assign":
        task_id = proposal.get("task_id")
        if task_id:
            return "confirm_schedule_plan", {"task_id": task_id}
        return None

    return None
