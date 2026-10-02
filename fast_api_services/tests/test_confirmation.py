"""
Tests for the shared confirmation / cancellation intent detector.

Regression guard: ordinary questions containing "có" / "không" must NOT be
mistaken for a confirmation (or cancellation) of a pending write action.
"""
from __future__ import annotations

import pytest

from fast_api_services.agent.confirmation import is_cancel, is_confirmation


@pytest.mark.parametrize(
    "text",
    ["xác nhận", "Xác nhận!", "đồng ý", "confirm", "yes", "ok", "ok nhé", "oke", "ừ"],
)
def test_explicit_confirmation_matches(text):
    assert is_confirmation(text) is True


@pytest.mark.parametrize(
    "text",
    [
        "",
        "có slot nào trống không?",
        "slot này có giám khảo chưa?",
        "giám khảo có sẵn không",
        "book giúp tôi",
        "xem lịch tháng 6",
        "không đồng ý",
        "không xác nhận",
    ],
)
def test_non_confirmation_does_not_match(text):
    assert is_confirmation(text) is False


@pytest.mark.parametrize("text", ["hủy", "huỷ", "hủy bỏ", "cancel", "thôi", "no"])
def test_explicit_cancel_matches(text):
    assert is_cancel(text) is True


@pytest.mark.parametrize(
    "text",
    ["", "có slot nào không?", "xem lịch", "xác nhận"],
)
def test_non_cancel_does_not_match(text):
    assert is_cancel(text) is False
