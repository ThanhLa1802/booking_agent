"""Tests for the grounding guard (P0)."""
from fast_api_services.agent.grounding import (
    extract_numbers,
    find_ungrounded_numbers,
    is_grounded,
)


class TestExtractNumbers:
    def test_basic(self):
        assert "800000" in extract_numbers("Học phí 800,000 VND")

    def test_normalizes_separators(self):
        assert extract_numbers("1.234.567") == ["1234567"]


class TestGrounding:
    def test_grounded_when_number_in_source(self):
        sources = ["[1] Piano Grade 1 | Fee: 800000 VND"]
        assert is_grounded("Học phí là 800000 VND", sources) is True

    def test_ungrounded_when_number_absent(self):
        sources = ["[1] Piano Grade 1 | Fee: 800000 VND"]
        ungrounded = find_ungrounded_numbers("Học phí là 950000 VND", sources)
        assert "950000" in ungrounded

    def test_short_numbers_ignored(self):
        # Grade numbers (1–8) must not trigger the guard.
        assert find_ungrounded_numbers("Grade 5 piano", ["no numbers here"]) == []

    def test_format_mismatch_still_grounded(self):
        # Answer uses separators; source doesn't.
        sources = ["Fee: 800000"]
        assert is_grounded("Fee: 800,000", sources) is True
