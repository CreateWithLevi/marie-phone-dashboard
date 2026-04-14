"""
Agent 2: Call Analyzer — LLM-based structured extraction

Input:  Transcript text (from Agent 1)
Output: {
    "first_name": str,
    "last_name": str,
    "email": str,
    "phone": str,
    "case_type": str,
    "urgency": int (1-5),
    "key_facts": list[str],
    "summary": str,
    "resolution_status": str,
    "confidence_scores": dict
}

Limitations:
- LLM may hallucinate contact details not in transcript
- Email/phone reconstruction from spelled-out characters is imperfect
- Case type classification depends on transcript quality

Mitigations:
- Confidence scores per field flag uncertain extractions
- needs_human_review flag for low-confidence results
- Ground truth comparison via evaluate command
"""

import json
from pathlib import Path

from pipeline.llm_client import llm_generate_json


PROMPT_PATH = Path(__file__).parent / "prompts" / "analyze_call.txt"

VALID_CASE_TYPES = {
    "Family Law",
    "Traffic Law",
    "Employment Law",
    "Landlord-Tenant",
    "Criminal Law",
    "Immigration",
    "Contract Dispute",
    "General Inquiry",
}

VALID_RESOLUTION_STATUSES = {
    "resolved",
    "needs_followup",
    "appointment_booked",
    "dropped",
}


def analyze_call(transcript: str) -> dict:
    """Analyze a call transcript and extract structured data.

    Args:
        transcript: Full transcript text from Agent 1

    Returns:
        dict with extracted fields + confidence scores
    """
    prompt_template = PROMPT_PATH.read_text()
    prompt = prompt_template.replace("{transcript}", transcript)

    result = llm_generate_json(prompt)

    # Normalize and validate
    result = _normalize(result)
    result["needs_human_review"] = _should_flag_for_review(result)

    return result


def _normalize(data: dict) -> dict:
    """Normalize LLM output to match expected schema."""
    # Ensure case_type is valid
    case_type = data.get("case_type", "General Inquiry")
    if case_type not in VALID_CASE_TYPES:
        case_type = "General Inquiry"
    data["case_type"] = case_type

    # Ensure resolution_status is valid
    status = data.get("resolution_status", "needs_followup")
    if status not in VALID_RESOLUTION_STATUSES:
        status = "needs_followup"
    data["resolution_status"] = status

    # Clamp urgency to 1-5
    urgency = data.get("urgency", 3)
    try:
        urgency = max(1, min(5, int(urgency)))
    except (ValueError, TypeError):
        urgency = 3
    data["urgency"] = urgency

    # Ensure key_facts is a list
    if not isinstance(data.get("key_facts"), list):
        data["key_facts"] = []

    # Ensure confidence_scores exist
    default_scores = {
        "first_name": 0.5,
        "last_name": 0.5,
        "email": 0.5,
        "phone": 0.5,
        "case_type": 0.5,
    }
    scores = data.get("confidence_scores", {})
    if not isinstance(scores, dict):
        scores = {}
    for key, default in default_scores.items():
        if key not in scores:
            scores[key] = default
        try:
            scores[key] = max(0.0, min(1.0, float(scores[key])))
        except (ValueError, TypeError):
            scores[key] = default
    data["confidence_scores"] = scores

    # Clean string fields
    for field in ("first_name", "last_name", "email", "phone", "summary"):
        data[field] = str(data.get(field, "") or "").strip()

    return data


def _should_flag_for_review(data: dict) -> bool:
    """Determine if this call needs human review.

    Flags when any contact field has low confidence,
    since contact accuracy is critical for follow-up.
    """
    scores = data.get("confidence_scores", {})
    # Flag if any contact field confidence < 0.6
    contact_fields = ["first_name", "last_name", "email", "phone"]
    for field in contact_fields:
        if scores.get(field, 0) < 0.6:
            return True
    return False


def analyze_batch(transcripts: list[dict]) -> list[dict]:
    """Analyze a batch of transcripts.

    Args:
        transcripts: List of dicts with "call_id" and "text" keys

    Returns:
        List of dicts with call_id + analysis results
    """
    results = []
    for item in transcripts:
        call_id = item["call_id"]
        print(f"  Analyzing {call_id}...", end=" ", flush=True)

        try:
            analysis = analyze_call(item["text"])
            analysis["call_id"] = call_id
            results.append(analysis)
            print("done")
        except Exception as e:
            print(f"error: {e}")
            results.append({
                "call_id": call_id,
                "error": str(e),
                "needs_human_review": True,
            })

    return results
