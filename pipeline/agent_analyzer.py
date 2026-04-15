"""
Agent 2: Call Analyzer — LLM-based structured extraction with reflection loop

Pipeline: Guardrails → LLM Extraction → Tool Validation → Reflection → Output

Design patterns used:
- Pattern #32 (Guardrails): sanitize transcript before LLM
- Pattern #21 (Tool Calling): deterministic email/phone validation post-extraction
- Pattern #18 (Reflection): re-extract low-confidence fields with focused prompt

Input:  Transcript text (from Transcription Step)
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
    "confidence_scores": dict,
    "needs_human_review": bool,
    "reflection_applied": bool,
    "tool_corrections": list[str]
}
"""

import json
from pathlib import Path

from pipeline.guardrails import sanitize_transcript, validate_agent_output
from pipeline.llm_client import llm_generate_json
from pipeline.tools import apply_tools


PROMPT_PATH = Path(__file__).parent / "prompts" / "analyze_call.txt"
REFLECTION_PROMPT_PATH = Path(__file__).parent / "prompts" / "reflection.txt"

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

REFLECTION_THRESHOLD = 0.6
REFLECTABLE_FIELDS = ["first_name", "last_name", "email", "phone"]

REQUIRED_OUTPUT_FIELDS = [
    "first_name", "last_name", "email", "phone",
    "case_type", "urgency", "summary", "confidence_scores",
]


def analyze_call(transcript: str, enable_reflection: bool = True) -> dict:
    """Analyze a call transcript with guardrails, tools, and reflection.

    Flow:
        1. Guardrails: sanitize transcript
        2. LLM: first extraction pass
        3. Normalize: validate schema
        4. Tools: validate email, format phone, check completeness
        5. Reflection: re-extract low-confidence fields (if any)
        6. Flag: determine if human review needed
    """
    sanitized = sanitize_transcript(transcript)
    if sanitized["blocked"]:
        return {
            "error": f"Transcript blocked: {sanitized['warnings']}",
            "needs_human_review": True,
            "reflection_applied": False,
            "tool_corrections": [],
        }
    transcript_clean = sanitized["text"]

    prompt_template = PROMPT_PATH.read_text()
    prompt = prompt_template.replace("{transcript}", transcript_clean)
    result = llm_generate_json(prompt)

    result = _normalize(result)

    validation = validate_agent_output(result, REQUIRED_OUTPUT_FIELDS)
    if not validation["valid"]:
        result["_output_warnings"] = validation["missing_fields"]

    result = apply_tools(result)

    tool_corrections = []
    tr = result.get("tool_results", {})
    for tool_name in ("email_validation", "phone_formatting"):
        corrections = tr.get(tool_name, {}).get("corrections", [])
        tool_corrections.extend(corrections)
    result["tool_corrections"] = tool_corrections

    result["reflection_applied"] = False
    if enable_reflection:
        low_conf_fields = _get_low_confidence_fields(result)
        if low_conf_fields:
            result = _reflect(transcript_clean, result, low_conf_fields)
            result["reflection_applied"] = True

    result["needs_human_review"] = _should_flag_for_review(result)

    result.pop("tool_results", None)
    result.pop("_output_warnings", None)

    return result


def _get_low_confidence_fields(data: dict) -> list[str]:
    scores = data.get("confidence_scores", {})
    return [
        field for field in REFLECTABLE_FIELDS
        if scores.get(field, 0) < REFLECTION_THRESHOLD
    ]


def _reflect(transcript: str, first_result: dict, low_conf_fields: list[str]) -> dict:
    """Re-extract low-confidence fields with a focused reflection prompt.

    Pattern #18 (Reflection): The LLM sees its own first attempt and
    specific guidance on what to improve. This creates a feedback loop
    that improves extraction quality.
    """
    prompt_template = REFLECTION_PROMPT_PATH.read_text()

    previous = {f: first_result.get(f, "") for f in low_conf_fields}
    previous["confidence_scores"] = {
        f: first_result.get("confidence_scores", {}).get(f, 0)
        for f in low_conf_fields
    }

    prompt = (
        prompt_template
        .replace("{previous_result}", json.dumps(previous, indent=2, ensure_ascii=False))
        .replace("{low_confidence_fields}", json.dumps(low_conf_fields))
        .replace("{transcript}", transcript)
    )

    try:
        reflection = llm_generate_json(prompt)
    except Exception:
        return first_result

    reflection_scores = reflection.get("confidence_scores", {})
    original_scores = first_result.get("confidence_scores", {})

    for field in low_conf_fields:
        new_val = reflection.get(field)
        new_conf = reflection_scores.get(field, 0)
        old_conf = original_scores.get(field, 0)

        if new_val and new_conf > old_conf:
            first_result[field] = new_val
            first_result["confidence_scores"][field] = new_conf

    first_result = apply_tools(first_result)
    tr = first_result.get("tool_results", {})
    for tool_name in ("email_validation", "phone_formatting"):
        corrections = tr.get(tool_name, {}).get("corrections", [])
        for c in corrections:
            if c not in first_result.get("tool_corrections", []):
                first_result.setdefault("tool_corrections", []).append(c)

    return first_result


def _normalize(data: dict) -> dict:
    case_type = data.get("case_type", "General Inquiry")
    if case_type not in VALID_CASE_TYPES:
        case_type = "General Inquiry"
    data["case_type"] = case_type

    status = data.get("resolution_status", "needs_followup")
    if status not in VALID_RESOLUTION_STATUSES:
        status = "needs_followup"
    data["resolution_status"] = status

    urgency = data.get("urgency", 3)
    try:
        urgency = max(1, min(5, int(urgency)))
    except (ValueError, TypeError):
        urgency = 3
    data["urgency"] = urgency

    if not isinstance(data.get("key_facts"), list):
        data["key_facts"] = []

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

    for field in ("first_name", "last_name", "email", "phone", "summary"):
        data[field] = str(data.get(field, "") or "").strip()

    return data


def _should_flag_for_review(data: dict) -> bool:
    scores = data.get("confidence_scores", {})
    contact_fields = ["first_name", "last_name", "email", "phone"]
    for field in contact_fields:
        if scores.get(field, 0) < REFLECTION_THRESHOLD:
            return True
    return False


def analyze_batch(transcripts: list[dict], enable_reflection: bool = True) -> list[dict]:
    results = []
    for item in transcripts:
        call_id = item["call_id"]
        print(f"  Analyzing {call_id}...", end=" ", flush=True)

        try:
            analysis = analyze_call(item["text"], enable_reflection=enable_reflection)
            analysis["call_id"] = call_id
            results.append(analysis)
            reflected = " (reflected)" if analysis.get("reflection_applied") else ""
            print(f"done{reflected}")
        except Exception as e:
            print(f"error: {e}")
            results.append({
                "call_id": call_id,
                "error": str(e),
                "needs_human_review": True,
            })

    return results
