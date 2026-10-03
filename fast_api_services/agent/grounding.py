"""
Grounding guard (P0).

Detects numbers in the model's answer that do NOT appear in any tool output for
the same turn. This is a cheap, deterministic defence against the assistant
inventing fees, dates, slot counts or booking IDs.

It is intentionally conservative: only "significant" numbers (>= ``min_digits``)
are checked, so grades (1–8) and short tokens don't trigger false positives.
"""
from __future__ import annotations

import re

_NUMBER_RE = re.compile(r"\d[\d.,]*")


def _normalize(token: str) -> str:
    return token.replace(".", "").replace(",", "")


def extract_numbers(text: str) -> list[str]:
    """Return normalized digit runs found in *text*."""
    return [_normalize(m.group()) for m in _NUMBER_RE.finditer(text or "")]


def find_ungrounded_numbers(
    answer: str, sources: list[str], min_digits: int = 4
) -> list[str]:
    """Numbers in *answer* that do not occur in any of *sources*."""
    source_blob = _normalize(" ".join(s or "" for s in sources))
    ungrounded: list[str] = []
    for number in extract_numbers(answer):
        if len(number) < min_digits:
            continue
        if number in source_blob:
            continue
        ungrounded.append(number)
    return ungrounded


def is_grounded(answer: str, sources: list[str], min_digits: int = 4) -> bool:
    return not find_ungrounded_numbers(answer, sources, min_digits=min_digits)
