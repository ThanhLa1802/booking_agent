"""
Audit logging helper.

``log_action`` is best-effort: an audit failure must never break the operation
it is recording, so it swallows and logs exceptions.
"""
from __future__ import annotations

import logging

from .models import AuditLog

logger = logging.getLogger(__name__)


def _client_ip(request) -> str | None:
    if request is None:
        return None
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR")


def log_action(
    *,
    actor=None,
    action: str,
    entity_type: str = "",
    entity_id=None,
    metadata: dict | None = None,
    request=None,
) -> None:
    try:
        AuditLog.objects.create(
            actor=actor if getattr(actor, "is_authenticated", False) else None,
            action=action,
            entity_type=entity_type,
            entity_id="" if entity_id is None else str(entity_id),
            metadata=metadata or {},
            ip_address=_client_ip(request),
        )
    except Exception as exc:  # never let auditing break the request
        logger.warning("audit log_action failed: %s", exc)
