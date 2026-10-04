"""
Deterministic scope/role guard (defense-in-depth).

Runs in the router BEFORE the ReAct agent so a few high-confidence cases never
reach the LLM:

  * a non-admin (STUDENT/PARENT/...) asking for admin-only scheduling data or
    claiming admin authority (danh sách giám khảo, gán giám khảo, xếp lịch, ...);
  * clearly off-topic requests (code, arithmetic, weather, jokes, ...).

It is intentionally conservative: only unambiguous patterns match, everything
else falls through to the prompt-level policy. It is NOT a security boundary —
it cannot cause a write; the write gate (``authorization.authorize_write``) is.
"""
from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class ScopeDecision:
    reply: str


# Admin-only actions a non-admin must never get help with.
_ADMIN_ACTION_RE = re.compile(
    r"danh\s*sách\s*(các\s*)?(giám\s*khảo|giáo\s*viên)"
    r"|liệt\s*kê\s*(các\s*)?(giám\s*khảo|giáo\s*viên)"
    r"|(gán|phân\s*công|đổi)\s*(giám\s*khảo|giáo\s*viên)"
    r"|xếp\s*lịch|batch\s*schedule|assign\s*examiner|list\s*examiners"
    r"|lịch\s*(làm\s*việc\s*)?của\s*(các\s*)?(giám\s*khảo|giáo\s*viên)",
    re.IGNORECASE,
)

# A non-admin asserting admin identity.
_ROLE_CLAIM_RE = re.compile(
    r"(tôi|mình|i)\s+(là|am)\s+(một\s+)?(quản\s*trị|admin|center\s*admin|trưởng\s*trung\s*tâm)",
    re.IGNORECASE,
)

# Clearly off-topic intents (kept conservative to avoid false positives).
# The arithmetic alternative must NOT swallow dates like "2012-06-15", so a
# hyphen only counts when surrounded by spaces; + * / × ÷ count with or without.
_OFF_TOPIC_RE = re.compile(
    r"\bcode\b|\bpython\b|javascript|typescript|\bjava\b|c\+\+|c#|golang"
    r"|lập\s*trình|thuật\s*toán|viết\s*hàm|\bfunction\b|\bscript\b"
    r"|thời\s*tiết|\bweather\b|chuyện\s*cười|truyện\s*cười|\bjoke\b|kể\s*chuyện"
    r"|đạo\s*hàm|phương\s*trình"
    r"|\d+\s*[+*/×÷]\s*\d+|\d+\s+-\s+\d+"
    r"|tính\s*tổng\s*(2|hai)\s*số",
    re.IGNORECASE,
)

_ADMIN_DECLINE = (
    "Xin lỗi, tài khoản của bạn không có quyền quản trị trung tâm nên mình không thể "
    "xem/xếp lịch giám khảo. Mình có thể hỗ trợ bạn đặt lịch thi, tra cứu học phí hoặc "
    "lịch thi của bạn."
)
_OFF_TOPIC_DECLINE = (
    "Xin lỗi, mình chỉ hỗ trợ các việc liên quan tới kỳ thi Trinity (đặt lịch, học phí, "
    "lịch thi, chính sách). Bạn cần mình giúp gì về kỳ thi không?"
)


def classify_scope(message: str, user_role: str) -> ScopeDecision | None:
    """Return a fixed decline for a clear scope/role violation, else ``None``."""
    text = message or ""

    if user_role != "CENTER_ADMIN" and (
        _ROLE_CLAIM_RE.search(text) or _ADMIN_ACTION_RE.search(text)
    ):
        return ScopeDecision(_ADMIN_DECLINE)

    if _OFF_TOPIC_RE.search(text):
        return ScopeDecision(_OFF_TOPIC_DECLINE)

    return None
