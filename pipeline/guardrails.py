"""
Input Guardrails — Sanitize and validate data before LLM processing (Pattern #32)

Prevents prompt injection, truncates overly long inputs, and detects
anomalies that could compromise extraction quality.
"""

import re

# Max transcript length (chars) to send to LLM — prevents cost blowup
MAX_TRANSCRIPT_LENGTH = 5000

# Patterns that suggest prompt injection attempts
INJECTION_PATTERNS = [
    r"ignore\s+(all\s+)?previous\s+instructions",
    r"ignore\s+(all\s+)?above",
    r"you\s+are\s+now\s+a",
    r"system\s*:\s*",
    r"<\s*/?\s*system\s*>",
    r"```\s*(system|assistant)",
    r"IMPORTANT:\s*override",
]

_injection_re = re.compile(
    "|".join(INJECTION_PATTERNS), re.IGNORECASE
)


def sanitize_transcript(text: str) -> dict:
    """Sanitize a transcript before sending to LLM.

    Returns:
        dict with:
            - text: sanitized transcript
            - warnings: list of issues found
            - blocked: True if transcript should not be processed
    """
    warnings = []

    if not text or not text.strip():
        return {"text": "", "warnings": ["Empty transcript"], "blocked": True}

    text = text.strip()

    # Check for prompt injection
    if _injection_re.search(text):
        warnings.append("Potential prompt injection detected")
        return {"text": text, "warnings": warnings, "blocked": True}

    # Truncate overly long transcripts
    if len(text) > MAX_TRANSCRIPT_LENGTH:
        warnings.append(
            f"Transcript truncated from {len(text)} to {MAX_TRANSCRIPT_LENGTH} chars"
        )
        text = text[:MAX_TRANSCRIPT_LENGTH]

    # Check for suspiciously short transcripts (< 10 chars)
    if len(text) < 10:
        warnings.append("Transcript suspiciously short — may produce low-quality extraction")

    return {"text": text, "warnings": warnings, "blocked": False}


def validate_agent_output(data: dict, required_fields: list[str]) -> dict:
    """Validate that LLM output contains required fields and reasonable values.

    Returns:
        dict with:
            - valid: bool
            - missing_fields: list of missing required fields
            - warnings: list of issues
    """
    missing = [f for f in required_fields if f not in data or data[f] is None]
    warnings = []

    # Check for suspiciously long string values (possible hallucination)
    for key, val in data.items():
        if isinstance(val, str) and len(val) > 1000:
            warnings.append(f"Field '{key}' is suspiciously long ({len(val)} chars)")

    return {
        "valid": len(missing) == 0,
        "missing_fields": missing,
        "warnings": warnings,
    }
