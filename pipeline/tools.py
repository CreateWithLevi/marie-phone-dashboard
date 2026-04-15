"""
Deterministic Tools — Post-extraction validation and correction (Pattern #21)

These tools give the pipeline real "tool use" capabilities. After the LLM
extracts contact info, these tools validate and correct the output using
deterministic logic — no LLM needed.

This is the Tool Calling pattern: the LLM does the reasoning (extraction),
then tools handle what tools do best (validation, formatting, lookup).
"""

import re


# Common email domain typos and corrections
DOMAIN_CORRECTIONS = {
    "gmial.com": "gmail.com",
    "gmal.com": "gmail.com",
    "gamil.com": "gmail.com",
    "gmaill.com": "gmail.com",
    "gmail.de": "gmail.de",  # valid, keep
    "gmx.de": "gmx.de",  # valid, keep
    "hotmial.com": "hotmail.com",
    "hotmal.com": "hotmail.com",
    "yahooo.com": "yahoo.com",
    "yaho.com": "yahoo.com",
    "outllook.com": "outlook.com",
    "outlok.com": "outlook.com",
    "web.de": "web.de",  # valid, keep
    "t-onlien.de": "t-online.de",
    "t-onlie.de": "t-online.de",
}

EMAIL_RE = re.compile(r"^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$")

# German phone patterns
GERMAN_PHONE_RE = re.compile(r"^(\+49|0049|0)\s*\d[\d\s/\-\.]{6,}$")


def validate_email(email: str) -> dict:
    """Validate and attempt to correct an extracted email address.

    Returns:
        dict with:
            - original: input email
            - corrected: corrected email (or original if no correction)
            - valid: whether the result passes format validation
            - corrections: list of corrections applied
    """
    if not email or not email.strip():
        return {
            "original": email,
            "corrected": "",
            "valid": False,
            "corrections": ["Empty email"],
        }

    cleaned = email.strip().lower()
    corrections = []

    # Remove spaces within email (common Whisper artifact)
    if " " in cleaned and "@" in cleaned:
        cleaned = cleaned.replace(" ", "")
        corrections.append("Removed spaces")

    # Fix missing @ (common when Whisper hears "at" as text)
    if "@" not in cleaned:
        # Try common patterns: "name at domain.com"
        for sep in [" at ", " ett ", " ätt "]:  # German speakers may say "ett"
            if sep in cleaned:
                cleaned = cleaned.replace(sep, "@", 1)
                corrections.append(f"Replaced '{sep.strip()}' with '@'")
                break

    # Fix domain typos
    if "@" in cleaned:
        local, _, domain = cleaned.partition("@")
        if domain in DOMAIN_CORRECTIONS:
            corrected_domain = DOMAIN_CORRECTIONS[domain]
            if corrected_domain != domain:
                corrections.append(f"Domain corrected: {domain} → {corrected_domain}")
                domain = corrected_domain
        cleaned = f"{local}@{domain}"

    # Remove trailing dots (common artifact)
    cleaned = cleaned.rstrip(".")

    valid = bool(EMAIL_RE.match(cleaned))

    return {
        "original": email,
        "corrected": cleaned,
        "valid": valid,
        "corrections": corrections,
    }


def format_phone(phone: str, country: str = "DE") -> dict:
    """Normalize a phone number to a consistent format.

    Returns:
        dict with:
            - original: input phone
            - formatted: normalized phone number
            - valid: whether the result looks like a valid phone
            - corrections: list of corrections applied
    """
    if not phone or not phone.strip():
        return {
            "original": phone,
            "formatted": "",
            "valid": False,
            "corrections": ["Empty phone"],
        }

    cleaned = phone.strip()
    corrections = []

    # Remove common separators
    digits_only = re.sub(r"[\s\-\./\(\)]", "", cleaned)

    # Normalize German country code
    if digits_only.startswith("0049"):
        digits_only = "+49" + digits_only[4:]
        corrections.append("Normalized 0049 → +49")
    elif digits_only.startswith("49") and not digits_only.startswith("+"):
        digits_only = "+49" + digits_only[2:]
        corrections.append("Added + prefix to country code")
    elif digits_only.startswith("0") and country == "DE":
        digits_only = "+49" + digits_only[1:]
        corrections.append("Converted local format to +49")

    # Format: +49 XXX XXXXXXX
    if digits_only.startswith("+49") and len(digits_only) >= 12:
        rest = digits_only[3:]
        # Try to format as +49 XXX XXXXXXXX
        if len(rest) >= 10:
            formatted = f"+49 {rest[:3]} {rest[3:]}"
        else:
            formatted = f"+49 {rest}"
        corrections.append("Formatted to standard layout")
    else:
        formatted = digits_only

    valid = bool(re.match(r"^\+?\d{10,15}$", digits_only))

    return {
        "original": phone,
        "formatted": formatted,
        "valid": valid,
        "corrections": corrections,
    }


def check_contact_completeness(data: dict) -> dict:
    """Evaluate whether extracted contact info is sufficient for follow-up.

    Returns:
        dict with:
            - complete: bool (enough for follow-up?)
            - missing: list of missing critical fields
            - quality: "high" / "medium" / "low"
            - suggestions: list of improvement suggestions
    """
    missing = []
    suggestions = []

    name = f"{data.get('first_name', '')} {data.get('last_name', '')}".strip()
    email = data.get("email", "")
    phone = data.get("phone", "")

    if not name or name == "None":
        missing.append("name")
        suggestions.append("Caller name is missing — needs manual review of transcript")

    if not email:
        missing.append("email")
    elif not EMAIL_RE.match(email.lower()):
        suggestions.append(f"Email '{email}' may be invalid — verify format")

    if not phone:
        missing.append("phone")

    # At least one contact method needed
    has_contact = bool(email) or bool(phone)

    if not missing:
        quality = "high"
    elif has_contact and name:
        quality = "medium"
    else:
        quality = "low"

    return {
        "complete": len(missing) == 0,
        "missing": missing,
        "quality": quality,
        "suggestions": suggestions,
    }


def apply_tools(data: dict) -> dict:
    """Run all tools on Agent 2 output. Returns enhanced data with tool results.

    This is the main entry point — called after LLM extraction to validate
    and correct results using deterministic logic.
    """
    tool_results = {}

    # Validate and correct email
    email_result = validate_email(data.get("email", ""))
    tool_results["email_validation"] = email_result
    if email_result["corrected"] and email_result["corrected"] != data.get("email", ""):
        data["email"] = email_result["corrected"]

    # Format phone
    phone_result = format_phone(data.get("phone", ""))
    tool_results["phone_formatting"] = phone_result
    if phone_result["formatted"] and phone_result["formatted"] != data.get("phone", ""):
        data["phone"] = phone_result["formatted"]

    # Check completeness
    completeness = check_contact_completeness(data)
    tool_results["contact_completeness"] = completeness

    # Adjust confidence based on tool results
    scores = data.get("confidence_scores", {})
    if not email_result["valid"] and scores.get("email", 1.0) > 0.5:
        scores["email"] = min(scores.get("email", 1.0), 0.4)
    if not phone_result["valid"] and scores.get("phone", 1.0) > 0.5:
        scores["phone"] = min(scores.get("phone", 1.0), 0.4)
    data["confidence_scores"] = scores

    data["tool_results"] = tool_results
    return data
