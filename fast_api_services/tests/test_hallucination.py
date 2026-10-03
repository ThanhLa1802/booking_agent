"""
Hallucination-guard regression suite (deterministic, no LLM).

The grounding guard (``agent/grounding.py``) is the cheap, model-free defence
against the assistant inventing fees, dates, slot counts or booking IDs. These
tests pin its behaviour and document the known gaps.
"""
from __future__ import annotations

import pytest

from fast_api_services.agent.grounding import (
    extract_numbers,
    find_ungrounded_numbers,
    is_grounded,
)


class TestNumberExtraction:
    def test_vnd_grouping_with_dots(self):
        assert "1500000" in extract_numbers("Học phí 1.500.000 VND")

    def test_grouping_with_commas(self):
        assert "800000" in extract_numbers("Fee: 800,000")

    def test_decimal_with_separators(self):
        assert extract_numbers("1.500.000,50") == ["150000050"]

    def test_hyphenated_date_splits_into_parts(self):
        # Documents current behaviour: a date is tokenised into year/month/day.
        assert extract_numbers("2026-05-10") == ["2026", "05", "10"]


class TestGroundingFees:
    def test_grounded_fee_with_separator_mismatch(self):
        assert is_grounded("Học phí 1.500.000 VND", ["Fee: 1500000 VND"]) is True

    def test_invented_fee_flagged(self):
        ungrounded = find_ungrounded_numbers(
            "Học phí là 2.000.000 VND", ["Fee: 1500000 VND"]
        )
        assert "2000000" in ungrounded

    def test_grounded_from_any_source(self):
        sources = ["Piano Grade 1", "Fee: 900000 VND"]
        assert is_grounded("Phí 900000", sources) is True


class TestGroundingIds:
    def test_invented_booking_id_flagged(self):
        ungrounded = find_ungrounded_numbers(
            "Booking #5678 đã hủy", ["Booking #1234 cancelled"]
        )
        assert "5678" in ungrounded

    def test_matching_booking_id_grounded(self):
        assert is_grounded("Booking #1234 đã hủy", ["Booking #1234 cancelled"]) is True


class TestGroundingEdges:
    def test_empty_answer_is_grounded(self):
        assert is_grounded("", ["anything"]) is True

    def test_none_sources_ignored(self):
        ungrounded = find_ungrounded_numbers("100000", [None, "", "no numbers"])
        assert "100000" in ungrounded

    def test_min_digits_threshold(self):
        # A 3-digit number is below the default threshold and never flagged.
        assert find_ungrounded_numbers("abc 999", ["xyz"]) == []
        # ...but it is flagged once the threshold is lowered.
        assert find_ungrounded_numbers("abc 999", ["xyz"], min_digits=3) == ["999"]

    def test_short_grades_ignored(self):
        assert find_ungrounded_numbers("Grade 5 piano", ["no numbers"]) == []


class TestKnownGaps:
    @pytest.mark.xfail(
        reason="date hallucination is not caught: only the 4-digit year is checked, "
        "and the year usually matches the source, so a wrong month/day slips through",
        strict=False,
    )
    def test_hallucinated_date_is_flagged(self):
        ungrounded = find_ungrounded_numbers(
            "Kỳ thi ngày 2026-06-15", ["Exam on 2026-05-10"]
        )
        assert "20260615" in ungrounded
