"""Unit tests for pipeline/agent_analyzer.py deterministic helpers.

`_normalize()` is the schema enforcement layer that runs after every LLM call
in the Analyzer Agent. Its contract with downstream stages (quality gate,
reflection, seed_data loader, Django serializers) is strict:

  * case_type MUST be one of VALID_CASE_TYPES (or fall back to General Inquiry)
  * resolution_status MUST be one of VALID_RESOLUTION_STATUSES
  * urgency MUST be an int in [1, 5]
  * key_facts MUST be a list
  * confidence_scores MUST be a dict with all 5 keys, each in [0.0, 1.0]
  * first_name / last_name / email / phone / summary MUST be strings

If _normalize lets bad data through, later stages crash. These tests lock the
contract so the LLM can return anything and the pipeline stays stable.
"""

import pytest

from pipeline.agent_analyzer import (
    VALID_CASE_TYPES,
    VALID_RESOLUTION_STATUSES,
    _normalize,
)


class TestNormalizeCaseType:
    """case_type — validated against a fixed enum of legal categories."""

    @pytest.mark.parametrize("case_type", sorted(VALID_CASE_TYPES))
    def test_every_valid_case_type_is_preserved(self, case_type):
        """All 8 legal case types in VALID_CASE_TYPES must pass through unchanged."""
        result = _normalize({"case_type": case_type})
        assert result["case_type"] == case_type

    def test_unknown_case_type_falls_back_to_general_inquiry(self):
        """An LLM-invented category must not leak into downstream code."""
        result = _normalize({"case_type": "Intergalactic Law"})
        assert result["case_type"] == "General Inquiry"

    def test_missing_case_type_defaults_to_general_inquiry(self):
        """When the LLM omits case_type entirely, default to the safest bucket."""
        result = _normalize({})
        assert result["case_type"] == "General Inquiry"

    def test_case_type_is_case_sensitive(self):
        """'family law' is not the same as 'Family Law' — fallback should trigger."""
        result = _normalize({"case_type": "family law"})
        assert result["case_type"] == "General Inquiry"


class TestNormalizeResolutionStatus:
    """resolution_status — validated against a fixed state machine."""

    @pytest.mark.parametrize("status", sorted(VALID_RESOLUTION_STATUSES))
    def test_every_valid_status_is_preserved(self, status):
        """All 4 resolution states must pass through unchanged."""
        result = _normalize({"resolution_status": status})
        assert result["resolution_status"] == status

    def test_invalid_status_falls_back_to_needs_followup(self):
        """Unknown status → needs_followup (the safest default — forces attention)."""
        result = _normalize({"resolution_status": "completely_made_up"})
        assert result["resolution_status"] == "needs_followup"

    def test_missing_status_defaults_to_needs_followup(self):
        """When resolution_status is absent, default to the 'needs attention' state."""
        result = _normalize({})
        assert result["resolution_status"] == "needs_followup"


class TestNormalizeUrgency:
    """urgency — an integer clamped to [1, 5]."""

    @pytest.mark.parametrize("value,expected", [(1, 1), (2, 2), (3, 3), (4, 4), (5, 5)])
    def test_in_range_values_are_preserved(self, value, expected):
        """Integers 1-5 pass through unchanged — the core valid range."""
        assert _normalize({"urgency": value})["urgency"] == expected

    def test_urgency_is_clamped_above(self):
        """Values over 5 snap down to the max."""
        assert _normalize({"urgency": 99})["urgency"] == 5

    def test_urgency_is_clamped_below(self):
        """Values under 1 snap up to the min."""
        assert _normalize({"urgency": -3})["urgency"] == 1

    def test_zero_clamps_to_one(self):
        """Zero is a plausible LLM mistake — clamp to the minimum, not reject."""
        assert _normalize({"urgency": 0})["urgency"] == 1

    def test_numeric_string_is_coerced_to_int(self):
        """'4' should become 4 — LLMs often return numbers as strings."""
        assert _normalize({"urgency": "4"})["urgency"] == 4

    def test_float_is_coerced_to_int(self):
        """3.7 should truncate to 3 via int() — no rounding surprises."""
        assert _normalize({"urgency": 3.7})["urgency"] == 3

    def test_non_numeric_string_defaults_to_three(self):
        """Garbage input → middle of the range (3 = neutral)."""
        assert _normalize({"urgency": "not a number"})["urgency"] == 3

    def test_none_urgency_defaults_to_three(self):
        """Explicit None → default 3."""
        assert _normalize({"urgency": None})["urgency"] == 3

    def test_missing_urgency_defaults_to_three(self):
        """Absent key → default 3."""
        assert _normalize({})["urgency"] == 3


class TestNormalizeKeyFacts:
    """key_facts — must always be a list, never a string or None."""

    def test_valid_list_is_preserved(self):
        """A well-formed list of strings passes through unchanged."""
        facts = ["caller mentioned divorce", "two children involved"]
        result = _normalize({"key_facts": facts})
        assert result["key_facts"] == facts

    def test_empty_list_is_preserved(self):
        """An empty list is valid — the LLM legitimately found no facts."""
        result = _normalize({"key_facts": []})
        assert result["key_facts"] == []

    def test_string_becomes_empty_list(self):
        """LLMs sometimes return key_facts as a single string — coerce to []."""
        result = _normalize({"key_facts": "caller mentioned divorce"})
        assert result["key_facts"] == []

    def test_none_becomes_empty_list(self):
        """Explicit None → empty list."""
        result = _normalize({"key_facts": None})
        assert result["key_facts"] == []

    def test_missing_becomes_empty_list(self):
        """Absent key → empty list."""
        result = _normalize({})
        assert result["key_facts"] == []

    def test_dict_becomes_empty_list(self):
        """An unexpected dict shape → empty list (downstream expects iterable of strs)."""
        result = _normalize({"key_facts": {"a": 1}})
        assert result["key_facts"] == []


class TestNormalizeConfidenceScores:
    """confidence_scores — dict with 5 fixed keys, each clamped to [0.0, 1.0]."""

    REQUIRED_CONFIDENCE_FIELDS = ["first_name", "last_name", "email", "phone", "case_type"]

    def test_all_fields_in_unit_interval_are_preserved(self):
        """Happy path: well-formed confidence dict passes through."""
        scores = {f: 0.85 for f in self.REQUIRED_CONFIDENCE_FIELDS}
        result = _normalize({"confidence_scores": scores})
        for field in self.REQUIRED_CONFIDENCE_FIELDS:
            assert result["confidence_scores"][field] == 0.85

    def test_values_above_one_are_clamped_to_one(self):
        """Overconfident LLMs can't exceed 1.0."""
        result = _normalize({"confidence_scores": {"first_name": 1.5}})
        assert result["confidence_scores"]["first_name"] == 1.0

    def test_negative_values_are_clamped_to_zero(self):
        """Negative confidence makes no sense — clamp to 0."""
        result = _normalize({"confidence_scores": {"last_name": -0.2}})
        assert result["confidence_scores"]["last_name"] == 0.0

    def test_boundary_zero_and_one_are_preserved(self):
        """Exact boundary values must survive the clamp."""
        result = _normalize({
            "confidence_scores": {"first_name": 0.0, "last_name": 1.0}
        })
        assert result["confidence_scores"]["first_name"] == 0.0
        assert result["confidence_scores"]["last_name"] == 1.0

    def test_numeric_string_is_coerced_to_float(self):
        """LLMs sometimes emit '0.8' as a string — coerce via float()."""
        result = _normalize({"confidence_scores": {"email": "0.8"}})
        assert result["confidence_scores"]["email"] == 0.8

    def test_non_numeric_string_falls_back_to_default(self):
        """Garbage string → 0.5 (the field's default)."""
        result = _normalize({"confidence_scores": {"email": "high"}})
        assert result["confidence_scores"]["email"] == 0.5

    def test_none_value_falls_back_to_default(self):
        """Explicit None → default."""
        result = _normalize({"confidence_scores": {"phone": None}})
        assert result["confidence_scores"]["phone"] == 0.5

    def test_missing_fields_get_default_value(self):
        """All 5 required fields must be present, even if the LLM omitted them."""
        result = _normalize({"confidence_scores": {"first_name": 0.9}})
        scores = result["confidence_scores"]
        for field in self.REQUIRED_CONFIDENCE_FIELDS:
            assert field in scores
            assert 0.0 <= scores[field] <= 1.0
        assert scores["first_name"] == 0.9
        assert scores["last_name"] == 0.5

    def test_missing_confidence_scores_key_produces_full_defaults(self):
        """No confidence_scores at all → all 5 fields defaulted to 0.5."""
        result = _normalize({})
        scores = result["confidence_scores"]
        for field in self.REQUIRED_CONFIDENCE_FIELDS:
            assert scores[field] == 0.5

    def test_non_dict_confidence_scores_is_replaced_with_defaults(self):
        """If LLM returns a list/string/None for the whole dict, replace it."""
        for bad in [None, "high", ["first_name", 0.9], 42]:
            result = _normalize({"confidence_scores": bad})
            scores = result["confidence_scores"]
            assert isinstance(scores, dict)
            for field in self.REQUIRED_CONFIDENCE_FIELDS:
                assert scores[field] == 0.5


class TestNormalizeStringFields:
    """first_name / last_name / email / phone / summary — coerced to stripped strings."""

    @pytest.mark.parametrize(
        "field", ["first_name", "last_name", "email", "phone", "summary"]
    )
    def test_string_fields_default_to_empty_string_when_missing(self, field):
        """Downstream serializers expect str, never None — default to ''."""
        result = _normalize({})
        assert result[field] == ""
        assert isinstance(result[field], str)

    @pytest.mark.parametrize(
        "field", ["first_name", "last_name", "email", "phone", "summary"]
    )
    def test_none_string_field_becomes_empty_string(self, field):
        """Explicit None should coerce to '' rather than propagate."""
        result = _normalize({field: None})
        assert result[field] == ""

    def test_surrounding_whitespace_is_stripped_from_string_fields(self):
        """LLMs often emit leading/trailing whitespace — strip it."""
        result = _normalize({
            "first_name": "  Johanna  ",
            "email": "\tuser@gmail.com\n",
        })
        assert result["first_name"] == "Johanna"
        assert result["email"] == "user@gmail.com"
