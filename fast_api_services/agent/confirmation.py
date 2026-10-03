"""
Shared confirmation / cancellation intent detection for the human-in-the-loop gate.

The confirmation gate must only fire on an EXPLICIT, short command. Matching on
raw substrings (e.g. the Vietnamese word "có") is unsafe: an ordinary question
such as "slot này có giám khảo chưa?" would be mistaken for a "yes" and trigger a
write tool. We therefore match the keyword as a standalone word, and treat a
negated phrase ("không đồng ý") as a rejection rather than a confirmation.
"""
from __future__ import annotations

import re

_BOUNDARY_L = r"(?:^|[\s,.;:!?])"
_BOUNDARY_R = r"(?:$|[\s,.;:!?])"

_CONFIRM_RE = re.compile(
    _BOUNDARY_L
    + r"(xác nhận|đồng ý|confirm|yes|ok|oke|ừ|okay)"
    + _BOUNDARY_R,
    re.IGNORECASE,
)

_CANCEL_RE = re.compile(
    _BOUNDARY_L
    + r"(hủy|huỷ|huy|hủy bỏ|cancel|thôi|thoi|dừng|dung|no)"
    + _BOUNDARY_R,
    re.IGNORECASE,
)

# "không đồng ý" / "không xác nhận" = refusal, never a confirmation.
_NEGATED_CONFIRM_RE = re.compile(
    r"không\s+(?:đồng ý|xác nhận|confirm|yes|ok)",
    re.IGNORECASE,
)

# "không hủy" = keep it, never a cancellation.
_NEGATED_CANCEL_RE = re.compile(
    r"không\s+(?:hủy|huỷ|huy|cancel|thôi|dừng|dung)",
    re.IGNORECASE,
)

# A real confirmation/cancellation is a short command. A long sentence that
# merely mentions the keyword (e.g. "Tôi muốn xác nhận lại thông tin lịch thi")
# must NOT trip the gate.
_MAX_COMMAND_WORDS = 4

# Interrogatives never count as a command, even when short ("ok không?").
_QUESTION_RE = re.compile(
    r"[?？]|(?:^|\s)(?:không|chưa|gì|sao|nào|bao\s*giờ|khi\s*nào|thế\s*nào)(?=\s|$)",
    re.IGNORECASE,
)


def normalize(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip().lower())


def _is_short_command(normalized: str) -> bool:
    return len(normalized.split()) <= _MAX_COMMAND_WORDS


def is_confirmation(text: str) -> bool:
    """True only if *text* is an explicit, standalone confirmation command."""
    normalized = normalize(text)
    if not normalized or _NEGATED_CONFIRM_RE.search(normalized):
        return False
    if not _CONFIRM_RE.search(normalized):
        return False
    if _QUESTION_RE.search(normalized):
        return False
    return _is_short_command(normalized)


def is_cancel(text: str) -> bool:
    """True only if *text* is an explicit, standalone cancellation command."""
    normalized = normalize(text)
    if not normalized or _NEGATED_CANCEL_RE.search(normalized):
        return False
    if not _CANCEL_RE.search(normalized):
        return False
    if _QUESTION_RE.search(normalized):
        return False
    return _is_short_command(normalized)
