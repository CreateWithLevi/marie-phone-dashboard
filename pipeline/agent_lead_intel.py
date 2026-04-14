"""
Agent 3: Lead Intelligence — Lead scoring + resolution gap analysis

Input:  Structured call data (from Agent 2) + playbook questions (per case type)
Output: {
    "lead_score": int (0-100),
    "lead_score_reasoning": str,
    "resolution_gaps": list[str],
    "playbook_completeness": float (0-1.0),
    "playbook_answered": list[str],
    "playbook_unanswered": list[str],
    "recommended_actions": list[str],
    "priority_level": str ("high"/"medium"/"low")
}

Limitations:
- Scoring calibration limited by small sample (30 calls)
- Playbook evaluation depends on Agent 2 extraction quality
- No historical conversion data for training

Mitigations:
- Transparent reasoning (show why score was given)
- Lawyer can override score
- Priority level as actionable simplification of numeric score
"""

import json
from pathlib import Path

from pipeline.llm_client import llm_generate_json


PROMPT_PATH = Path(__file__).parent / "prompts" / "lead_intelligence.txt"

# Default playbook questions per case type (used when no custom playbook exists)
DEFAULT_PLAYBOOKS = {
    "Family Law": [
        "What specific family law issue? (divorce, custody, adoption, etc.)",
        "Are there children involved?",
        "Is there an existing court order?",
        "Is there an urgent deadline or safety concern?",
        "Has the caller already retained another attorney?",
    ],
    "Traffic Law": [
        "What type of traffic incident? (speeding, accident, DUI, etc.)",
        "When did the incident occur?",
        "Has a fine or penalty been issued?",
        "Is there a court date scheduled?",
        "Was anyone injured?",
    ],
    "Employment Law": [
        "What is the employment issue? (termination, discrimination, wage dispute, etc.)",
        "Is the caller the employee or employer?",
        "Is there a deadline for legal action?",
        "Has the employment relationship ended?",
        "Are there relevant documents (contract, termination letter)?",
    ],
    "Landlord-Tenant": [
        "Is the caller a landlord or tenant?",
        "What is the dispute about? (rent, repairs, eviction, deposit, etc.)",
        "Is there an active lease?",
        "Has notice been given?",
        "Is there a court deadline?",
    ],
    "Criminal Law": [
        "What are the charges or allegations?",
        "Has the caller been formally charged?",
        "Is there a court date?",
        "Is the caller currently detained?",
        "Has the caller spoken to police?",
    ],
    "Immigration": [
        "What type of immigration matter? (visa, asylum, deportation, etc.)",
        "What is the caller's current status?",
        "Are there filing deadlines?",
        "Has the caller received any official notices?",
        "Is the caller currently in Germany?",
    ],
    "Contract Dispute": [
        "What type of contract is involved?",
        "What is the nature of the dispute?",
        "What is the contract value?",
        "Has either party breached the contract?",
        "Is there a mediation or arbitration clause?",
    ],
    "General Inquiry": [
        "What is the general nature of the legal question?",
        "Has the caller attempted to resolve this themselves?",
        "Is there a time-sensitive element?",
    ],
}


def score_lead(call_data: dict, playbook_questions: list[str] | None = None) -> dict:
    """Score a lead and analyze resolution gaps.

    Args:
        call_data: Structured data from Agent 2 (must include case_type, key_facts, etc.)
        playbook_questions: Custom playbook questions. If None, uses defaults for case_type.

    Returns:
        dict with lead_score, reasoning, gaps, playbook analysis, actions, priority
    """
    case_type = call_data.get("case_type", "General Inquiry")

    if playbook_questions is None:
        playbook_questions = DEFAULT_PLAYBOOKS.get(case_type, DEFAULT_PLAYBOOKS["General Inquiry"])

    prompt_template = PROMPT_PATH.read_text()
    prompt = prompt_template.replace(
        "{call_data}", json.dumps(call_data, indent=2, ensure_ascii=False)
    ).replace(
        "{playbook_questions}", json.dumps(playbook_questions, indent=2, ensure_ascii=False)
    )

    result = llm_generate_json(prompt)
    return _normalize(result)


def _normalize(data: dict) -> dict:
    """Normalize LLM output to match expected schema."""
    # Clamp lead_score to 0-100
    score = data.get("lead_score", 50)
    try:
        score = max(0, min(100, int(score)))
    except (ValueError, TypeError):
        score = 50
    data["lead_score"] = score

    # Ensure string fields
    data["lead_score_reasoning"] = str(data.get("lead_score_reasoning", ""))

    # Ensure list fields
    for field in ("resolution_gaps", "playbook_answered", "playbook_unanswered", "recommended_actions"):
        if not isinstance(data.get(field), list):
            data[field] = []

    # Clamp playbook_completeness
    completeness = data.get("playbook_completeness", 0.0)
    try:
        completeness = max(0.0, min(1.0, float(completeness)))
    except (ValueError, TypeError):
        completeness = 0.0
    data["playbook_completeness"] = completeness

    # Validate priority_level
    priority = data.get("priority_level", "medium")
    if priority not in ("high", "medium", "low"):
        priority = "medium"
    data["priority_level"] = priority

    return data


def score_batch(analyzed_calls: list[dict]) -> list[dict]:
    """Score a batch of analyzed calls.

    Args:
        analyzed_calls: List of dicts from Agent 2 (with call_id)

    Returns:
        List of dicts with call_id + lead intelligence results
    """
    results = []
    for call in analyzed_calls:
        call_id = call.get("call_id", "unknown")
        print(f"  Scoring {call_id}...", end=" ", flush=True)

        try:
            score = score_lead(call)
            score["call_id"] = call_id
            results.append(score)
            print(f"done (score: {score['lead_score']})")
        except Exception as e:
            print(f"error: {e}")
            results.append({
                "call_id": call_id,
                "error": str(e),
                "lead_score": 0,
            })

    return results
