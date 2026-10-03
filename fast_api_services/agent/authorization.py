"""
Server-side authorization for write tools (P0 security boundary).

Threat: the LLM (or a prompt-injected instruction) can set ``confirm=True`` and
trigger a real write. The fix is to never treat the model's ``confirm`` argument
as the security boundary.

Instead:
  * When a write tool is first invoked without server authorization, it records
    a *pending action* in Redis and refuses to execute.
  * On the next user turn, the router checks whether the user's RAW message is an
    explicit confirmation. If so — and only then — it exposes the pending
    action's hash to the tools for that single turn.
  * A write tool executes only when its (tool_name, canonical args) hash is in
    the server-provided ``authorized_actions`` set.

The ``confirm`` flag is kept purely as UX signal; it is never sufficient.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any

# Argument keys that must NOT participate in the action signature (they describe
# the model's intent, not the action itself).
_IGNORED_KEYS = {"confirm"}


def canonical_args(args: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in (args or {}).items() if k not in _IGNORED_KEYS}


def action_hash(tool_name: str, args: dict[str, Any]) -> str:
    """Deterministic short hash of a write action (tool + canonical args)."""
    payload = json.dumps(
        {"tool": tool_name, "args": canonical_args(args)},
        sort_keys=True,
        default=str,
        separators=(",", ":"),
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:32]


def is_server_authorized(
    ctx: Any, tool_name: str, args: dict[str, Any]
) -> bool | None:
    """
    Return True/False when *ctx* carries a server-managed authorization set,
    or None when the context is unmanaged (legacy/test) so callers can fall
    back to the ``confirm`` flag.

    Production always supplies a real ``frozenset`` (possibly empty), so the
    boundary is always enforced there.
    """
    allowed = getattr(ctx, "authorized_actions", None)
    if isinstance(allowed, (set, frozenset)):
        return action_hash(tool_name, args) in allowed
    return None


async def _register_pending(ctx: Any, tool_name: str, args: dict[str, Any]) -> None:
    redis = getattr(ctx, "redis", None)
    user_id = getattr(ctx, "user_id", 0)
    if redis is None or not user_id:
        return
    try:
        from .memory import save_pending_action

        await save_pending_action(
            redis, user_id, tool_name, canonical_args(args), action_hash(tool_name, args)
        )
    except Exception:  # registration is best-effort; never break the tool
        pass


async def authorize_write(
    ctx: Any,
    tool_name: str,
    args: dict[str, Any],
    confirm: bool,
) -> bool:
    """
    Decide whether a write tool may proceed.

    * Server-managed ctx → only the pre-authorized hash passes; otherwise the
      action is recorded as pending so a genuine user confirmation can approve
      it on the next turn.
    * Unmanaged ctx (tests/legacy) → fall back to the ``confirm`` flag.
    """
    decision = is_server_authorized(ctx, tool_name, args)
    if decision is True:
        return True
    if decision is False:
        await _register_pending(ctx, tool_name, args)
        return False
    # Unmanaged context — legacy behaviour.
    if not confirm:
        await _register_pending(ctx, tool_name, args)
        return False
    return True
