"""
Quality Gate — LLM-as-Judge (Pattern #17)

An independent LLM call that audits Agent 2's extraction against the
original transcript. This is NOT self-assessment — it's a separate
evaluator that can catch hallucinations and inconsistencies.

Why independent judge?
- Agent 2's confidence scores are self-reported and tend to be overconfident
- A separate evaluator with a different prompt catches issues the extractor missed
- Provides a quality signal independent of confidence scores
"""

import json
from pathlib import Path

from pipeline.llm_client import llm_generate_json


PROMPT_PATH = Path(__file__).parent / "prompts" / "quality_gate.txt"


def audit_extraction(transcript: str, extraction: dict) -> dict:
    """Independently audit an extraction against the source transcript.

    Args:
        transcript: Original transcript text
        extraction: Agent 2 output to verify

    Returns:
        dict with:
            - quality_score: 1-5 overall score
            - faithfulness: 1-5 (is it grounded in transcript?)
            - completeness: 1-5 (did it capture everything?)
            - accuracy: 1-5 (are values correct?)
            - issues: list of specific problems
            - hallucinated_fields: list of field names that look made up
            - verdict: "accept" | "review" | "reject"
    """
    # Only pass the substantive fields to the judge, not metadata
    audit_fields = {
        k: v for k, v in extraction.items()
        if k in (
            "first_name", "last_name", "email", "phone",
            "case_type", "urgency", "key_facts", "summary",
            "resolution_status",
        )
    }

    prompt_template = PROMPT_PATH.read_text()
    prompt = (
        prompt_template
        .replace("{transcript}", transcript)
        .replace("{extraction}", json.dumps(audit_fields, indent=2, ensure_ascii=False))
    )

    try:
        result = llm_generate_json(prompt)
    except Exception as e:
        # Quality gate failure is non-fatal — default to "review"
        return {
            "quality_score": 0,
            "faithfulness": 0,
            "completeness": 0,
            "accuracy": 0,
            "issues": [f"Quality gate failed: {e}"],
            "hallucinated_fields": [],
            "verdict": "review",
        }

    return _normalize(result)


def _normalize(data: dict) -> dict:
    """Clamp scores and validate verdict."""
    for field in ("quality_score", "faithfulness", "completeness", "accuracy"):
        val = data.get(field, 0)
        try:
            val = max(0, min(5, int(val)))
        except (ValueError, TypeError):
            val = 0
        data[field] = val

    for field in ("issues", "hallucinated_fields"):
        if not isinstance(data.get(field), list):
            data[field] = []

    verdict = data.get("verdict", "review")
    if verdict not in ("accept", "review", "reject"):
        verdict = "review"
    data["verdict"] = verdict

    return data
