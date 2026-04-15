"""Unit tests for pipeline/tools.py — the deterministic validation layer.

These tools are Pattern #21 (Tool Calling) from Generative AI Design Patterns.
They handle what tools do best — validation, formatting, lookup — so the LLM
doesn't have to reason about deterministic rules.

The tests cover:
  * Real input shapes seen in the dataset (German speakers spelling emails,
    E.164 vs. local phone formats, common domain typos).
  * Behavior the Reflection loop depends on (confidence being auto-lowered
    when tools detect invalid data).
  * Contracts other pipeline stages rely on (apply_tools attaches
    tool_results and never silently drops fields).
"""

import pytest

from pipeline.tools import (
    apply_tools,
    check_contact_completeness,
    format_phone,
    validate_email,
)


class TestValidateEmail:
    """validate_email() — regex + domain typo correction + spoken-at handling."""

    def test_valid_email_passes_through_unchanged(self):
        """A well-formed email should be marked valid with no corrections."""
        result = validate_email("johanna.schmidt@gmail.com")
        assert result["valid"] is True
        assert result["corrected"] == "johanna.schmidt@gmail.com"
        assert result["corrections"] == []

    @pytest.mark.parametrize(
        "typo,expected",
        [
            ("user@gmial.com", "user@gmail.com"),
            ("user@gmal.com", "user@gmail.com"),
            ("user@gamil.com", "user@gmail.com"),
            ("user@gmaill.com", "user@gmail.com"),
            ("user@hotmial.com", "user@hotmail.com"),
            ("user@yahooo.com", "user@yahoo.com"),
            ("user@outllook.com", "user@outlook.com"),
            ("user@t-onlien.de", "user@t-online.de"),
        ],
    )
    def test_common_domain_typos_are_corrected(self, typo, expected):
        """Whisper transcription typos on common email domains should be fixed."""
        result = validate_email(typo)
        assert result["valid"] is True
        assert result["corrected"] == expected
        assert any("→" in c for c in result["corrections"])

    @pytest.mark.parametrize(
        "spoken",
        [
            "johanna at gmail.com",
            "johanna ett gmail.com",  # German speaker saying "at"
            "johanna ätt gmail.com",  # German speaker with umlaut variant
        ],
    )
    def test_spoken_at_is_reconstructed_to_at_sign(self, spoken):
        """Callers often say 'at' or 'ett' instead of the @ symbol."""
        result = validate_email(spoken)
        assert result["valid"] is True
        assert result["corrected"] == "johanna@gmail.com"
        assert any("@" in c for c in result["corrections"])

    def test_spaces_inside_email_are_removed(self):
        """Whisper may insert spaces around the @ sign."""
        result = validate_email("user @ gmail.com")
        assert result["valid"] is True
        assert result["corrected"] == "user@gmail.com"
        assert "Removed spaces" in result["corrections"]

    def test_trailing_dot_is_stripped(self):
        """Whisper sometimes appends a period at the end of a sentence."""
        result = validate_email("user@gmail.com.")
        assert result["valid"] is True
        assert result["corrected"] == "user@gmail.com"

    def test_uppercase_is_normalized_to_lowercase(self):
        """Email addresses are case-insensitive; normalize for comparison."""
        result = validate_email("Johanna.Schmidt@Gmail.COM")
        assert result["corrected"] == "johanna.schmidt@gmail.com"
        assert result["valid"] is True

    def test_empty_string_is_marked_invalid(self):
        """Empty input must not crash and must be flagged clearly."""
        result = validate_email("")
        assert result["valid"] is False
        assert result["corrected"] == ""
        assert "Empty email" in result["corrections"]

    def test_whitespace_only_is_marked_invalid(self):
        """Whitespace-only input is semantically empty."""
        result = validate_email("   \t\n  ")
        assert result["valid"] is False

    @pytest.mark.parametrize(
        "malformed",
        [
            "not-an-email",
            "missing-domain@",
            "@missing-local",
            "no-at-sign.com",
            "user@domain",  # missing TLD
            "user@@double.com",  # double @ sign
        ],
    )
    def test_malformed_emails_fail_validation(self, malformed):
        """Fundamentally malformed input should never be marked valid."""
        result = validate_email(malformed)
        assert result["valid"] is False

    def test_original_is_always_preserved_in_result(self):
        """Callers rely on 'original' to compare against the correction."""
        result = validate_email("user@gmial.com")
        assert result["original"] == "user@gmial.com"
        assert result["corrected"] == "user@gmail.com"


class TestFormatPhone:
    """format_phone() — E.164 normalization for German numbers."""

    def test_german_local_format_becomes_e164(self):
        """Local 0-prefixed numbers convert to +49 country code."""
        result = format_phone("0152 11223456")
        assert result["valid"] is True
        assert result["formatted"].startswith("+49")
        assert "152" in result["formatted"]
        assert any("+49" in c for c in result["corrections"])

    def test_0049_prefix_is_normalized_to_plus_49(self):
        """0049 and +49 are equivalent; canonicalize to +49."""
        result = format_phone("004915211223456")
        assert result["valid"] is True
        assert result["formatted"].startswith("+49")
        assert "0049" not in result["formatted"]
        assert any("0049" in c for c in result["corrections"])

    def test_49_without_plus_gets_plus_prepended(self):
        """A bare 49 prefix should be promoted to +49."""
        result = format_phone("4915211223456")
        assert result["valid"] is True
        assert result["formatted"].startswith("+49")

    def test_already_formatted_plus49_passes_through(self):
        """Valid E.164 input stays valid; only layout may change."""
        result = format_phone("+49 152 11223456")
        assert result["valid"] is True
        assert result["formatted"].startswith("+49")

    @pytest.mark.parametrize(
        "separator_style",
        [
            "+49-152-11223456",
            "+49.152.11223456",
            "+49 (152) 11223456",
            "+49/152/11223456",
        ],
    )
    def test_various_separators_are_all_stripped(self, separator_style):
        """Regardless of separator style, digits should survive normalization."""
        result = format_phone(separator_style)
        assert result["valid"] is True
        # Formatted output uses spaces only, no other separators
        cleaned = result["formatted"].replace(" ", "").replace("+", "")
        assert cleaned.isdigit()

    def test_empty_phone_is_marked_invalid(self):
        """Empty input must be handled gracefully."""
        result = format_phone("")
        assert result["valid"] is False
        assert result["formatted"] == ""
        assert "Empty phone" in result["corrections"]

    def test_too_short_number_is_marked_invalid(self):
        """Numbers shorter than 10 digits cannot be a real German phone."""
        result = format_phone("+49 123")
        assert result["valid"] is False

    def test_original_is_always_preserved_in_result(self):
        """Callers rely on 'original' to detect whether a correction occurred."""
        result = format_phone("0152 11223456")
        assert result["original"] == "0152 11223456"
        assert result["formatted"] != "0152 11223456"


class TestCheckContactCompleteness:
    """check_contact_completeness() — quality grading for contact info."""

    def test_all_fields_present_is_high_quality(self):
        """Name + email + phone is the ideal case."""
        result = check_contact_completeness({
            "first_name": "Johanna",
            "last_name": "Schmidt",
            "email": "johanna@gmail.com",
            "phone": "+49 152 11223456",
        })
        assert result["complete"] is True
        assert result["quality"] == "high"
        assert result["missing"] == []

    def test_missing_email_but_phone_present_is_medium(self):
        """A name plus one contact method is still followable."""
        result = check_contact_completeness({
            "first_name": "Johanna",
            "last_name": "Schmidt",
            "email": "",
            "phone": "+49 152 11223456",
        })
        assert result["complete"] is False
        assert result["quality"] == "medium"
        assert "email" in result["missing"]

    def test_missing_phone_but_email_present_is_medium(self):
        """Symmetry with the previous test — either contact method counts."""
        result = check_contact_completeness({
            "first_name": "Johanna",
            "last_name": "Schmidt",
            "email": "johanna@gmail.com",
            "phone": "",
        })
        assert result["quality"] == "medium"
        assert "phone" in result["missing"]

    def test_missing_everything_is_low_quality(self):
        """No name and no contact method → unfollowable."""
        result = check_contact_completeness({
            "first_name": "",
            "last_name": "",
            "email": "",
            "phone": "",
        })
        assert result["quality"] == "low"
        assert "name" in result["missing"]
        assert "email" in result["missing"]
        assert "phone" in result["missing"]

    def test_literal_none_string_is_treated_as_missing_name(self):
        """LLMs sometimes return the string 'None' — treat it as missing."""
        result = check_contact_completeness({
            "first_name": "None",
            "last_name": "",
            "email": "user@gmail.com",
            "phone": "+49 152 11223456",
        })
        assert "name" in result["missing"]

    def test_invalid_email_format_triggers_suggestion(self):
        """If an email is present but malformed, suggest verification."""
        result = check_contact_completeness({
            "first_name": "Johanna",
            "last_name": "Schmidt",
            "email": "not-an-email",
            "phone": "+49 152 11223456",
        })
        assert any("invalid" in s.lower() for s in result["suggestions"])


class TestApplyTools:
    """apply_tools() — the orchestrator that wires validators into Agent 2 output."""

    def test_invalid_email_lowers_confidence_below_threshold(self):
        """Reflection depends on this: invalid tools → confidence < 0.5 → retry."""
        data = {
            "email": "not-an-email",
            "phone": "+49 152 11223456",
            "confidence_scores": {"email": 0.9, "phone": 0.9},
        }
        result = apply_tools(data)
        assert result["confidence_scores"]["email"] <= 0.4

    def test_invalid_phone_lowers_phone_confidence(self):
        """Same contract as email — invalid phone triggers confidence drop."""
        data = {
            "email": "user@gmail.com",
            "phone": "garbage",
            "confidence_scores": {"email": 0.9, "phone": 0.9},
        }
        result = apply_tools(data)
        assert result["confidence_scores"]["phone"] <= 0.4

    def test_valid_data_preserves_high_confidence(self):
        """The tool must not punish correct extractions."""
        data = {
            "email": "user@gmail.com",
            "phone": "+49 152 11223456",
            "confidence_scores": {"email": 0.9, "phone": 0.9},
        }
        result = apply_tools(data)
        assert result["confidence_scores"]["email"] == 0.9
        assert result["confidence_scores"]["phone"] == 0.9

    def test_low_confidence_is_not_raised_even_when_invalid(self):
        """Tools only lower confidence — they never raise it."""
        data = {
            "email": "not-an-email",
            "phone": "+49 152 11223456",
            "confidence_scores": {"email": 0.2, "phone": 0.9},
        }
        result = apply_tools(data)
        # Was already 0.2, which is below the 0.5 threshold → stays 0.2
        assert result["confidence_scores"]["email"] == 0.2

    def test_domain_typo_rewrites_email_field_in_place(self):
        """After apply_tools, data['email'] should hold the corrected value."""
        data = {
            "email": "user@gmial.com",
            "phone": "+49 152 11223456",
            "confidence_scores": {"email": 0.9, "phone": 0.9},
        }
        result = apply_tools(data)
        assert result["email"] == "user@gmail.com"

    def test_phone_normalization_rewrites_phone_field_in_place(self):
        """Same contract as email — phone gets the formatted version."""
        data = {
            "email": "user@gmail.com",
            "phone": "004915211223456",
            "confidence_scores": {"email": 0.9, "phone": 0.9},
        }
        result = apply_tools(data)
        assert result["phone"].startswith("+49")
        assert "0049" not in result["phone"]

    def test_tool_results_dict_is_attached_to_output(self):
        """Downstream (reflection, quality gate, frontend) reads tool_results."""
        data = {
            "email": "user@gmail.com",
            "phone": "+49 152 11223456",
            "confidence_scores": {},
        }
        result = apply_tools(data)
        assert "tool_results" in result
        assert "email_validation" in result["tool_results"]
        assert "phone_formatting" in result["tool_results"]
        assert "contact_completeness" in result["tool_results"]

    def test_missing_confidence_scores_key_does_not_crash(self):
        """Defensive: Agent 2 output may lack the confidence dict entirely."""
        data = {
            "email": "user@gmail.com",
            "phone": "+49 152 11223456",
        }
        result = apply_tools(data)
        assert "confidence_scores" in result
