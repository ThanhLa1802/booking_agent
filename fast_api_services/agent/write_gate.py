"""
Compute the server-authorized action set for a single conversation turn.

A write executes only when its ``(tool, args)`` hash is in this set. The set is
populated on an explicit confirmation turn from either:

  * a ``pending_action`` recorded when the model first tried the write, or
  * the write implied by a stored scheduling ``pending_proposal``.

This is the single place the router uses to decide what the model is allowed to
write this turn, so it is unit-tested directly (see test_security_boundary_*).
"""
from __future__ import annotations

from typing import Optional

from .authorization import action_hash
from .proposals import proposal_to_action


def compute_authorized_actions(
    pending_action: Optional[dict],
    pending_proposal: Optional[dict],
    is_confirm_msg: bool,
) -> frozenset[str]:
    """Return the hashes the model may execute this turn (empty if not confirming)."""
    if not is_confirm_msg:
        return frozenset()

    authorized: set[str] = set()

    if pending_action and pending_action.get("hash"):
        authorized.add(pending_action["hash"])

    if pending_proposal:
        action = proposal_to_action(pending_proposal.get("proposal") or {})
        if action:
            authorized.add(action_hash(*action))

    return frozenset(authorized)
