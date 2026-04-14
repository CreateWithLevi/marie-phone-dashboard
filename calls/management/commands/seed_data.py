"""
Load pre-processed pipeline output (seed data) into the database.

This lets reviewers run the dashboard without Whisper or LLM installed:
    python manage.py seed_data

Expects JSON files in data/seed/:
    - transcripts.json  (Agent 1 output)
    - analyses.json     (Agent 2 output)
    - lead_scores.json  (Agent 3 output)
"""

import json
from pathlib import Path

from django.core.management.base import BaseCommand

from calls.models import Call, CaseType, Playbook, PlaybookQuestion, Transcript


SEED_DIR = Path(__file__).resolve().parent.parent.parent.parent / "data" / "seed"
GROUND_TRUTH_PATH = SEED_DIR.parent / "ground_truth.json"

# Default playbooks to create for each case type
DEFAULT_PLAYBOOKS = {
    "Family Law": {
        "description": "Intake for divorce, custody, adoption, and family disputes",
        "questions": [
            "What specific family law issue? (divorce, custody, adoption, etc.)",
            "Are there children involved?",
            "Is there an existing court order?",
            "Is there an urgent deadline or safety concern?",
            "Has the caller already retained another attorney?",
        ],
    },
    "Traffic Law": {
        "description": "Intake for speeding, accidents, DUI, and traffic violations",
        "questions": [
            "What type of traffic incident? (speeding, accident, DUI, etc.)",
            "When did the incident occur?",
            "Has a fine or penalty been issued?",
            "Is there a court date scheduled?",
            "Was anyone injured?",
        ],
    },
    "Employment Law": {
        "description": "Intake for termination, discrimination, and wage disputes",
        "questions": [
            "What is the employment issue? (termination, discrimination, wage dispute, etc.)",
            "Is the caller the employee or employer?",
            "Is there a deadline for legal action?",
            "Has the employment relationship ended?",
            "Are there relevant documents (contract, termination letter)?",
        ],
    },
    "Landlord-Tenant": {
        "description": "Intake for rent disputes, evictions, repairs, and deposits",
        "questions": [
            "Is the caller a landlord or tenant?",
            "What is the dispute about? (rent, repairs, eviction, deposit, etc.)",
            "Is there an active lease?",
            "Has notice been given?",
            "Is there a court deadline?",
        ],
    },
    "Criminal Law": {
        "description": "Intake for criminal charges and defense matters",
        "questions": [
            "What are the charges or allegations?",
            "Has the caller been formally charged?",
            "Is there a court date?",
            "Is the caller currently detained?",
            "Has the caller spoken to police?",
        ],
    },
    "Immigration": {
        "description": "Intake for visa, asylum, deportation, and residency matters",
        "questions": [
            "What type of immigration matter? (visa, asylum, deportation, etc.)",
            "What is the caller's current status?",
            "Are there filing deadlines?",
            "Has the caller received any official notices?",
            "Is the caller currently in Germany?",
        ],
    },
    "Contract Dispute": {
        "description": "Intake for contract breaches and commercial disputes",
        "questions": [
            "What type of contract is involved?",
            "What is the nature of the dispute?",
            "What is the contract value?",
            "Has either party breached the contract?",
            "Is there a mediation or arbitration clause?",
        ],
    },
    "General Inquiry": {
        "description": "General legal questions not fitting other categories",
        "questions": [
            "What is the general nature of the legal question?",
            "Has the caller attempted to resolve this themselves?",
            "Is there a time-sensitive element?",
        ],
    },
}


class Command(BaseCommand):
    help = "Load seed data from pipeline output into the database"

    def handle(self, *args, **options):
        self.stdout.write("Loading seed data...")

        # 1. Create case types + playbooks
        self._create_case_types_and_playbooks()

        # 2. Load ground truth
        ground_truth = self._load_ground_truth()

        # 3. Load pipeline outputs
        transcripts = self._load_json("transcripts.json")
        analyses = self._load_json("analyses.json")
        lead_scores = self._load_json("lead_scores.json")

        # Index by call_id
        analysis_map = {a["call_id"]: a for a in analyses if "error" not in a}
        score_map = {s["call_id"]: s for s in lead_scores if "error" not in s}

        # 4. Create Call + Transcript records
        created = 0
        for t in transcripts:
            call_id = t["call_id"]
            analysis = analysis_map.get(call_id, {})
            scores = score_map.get(call_id, {})
            gt = ground_truth.get(call_id, {})

            call = self._create_call(call_id, t, analysis, scores, gt)
            if call:
                created += 1

        self.stdout.write(self.style.SUCCESS(
            f"Loaded {created} calls with transcripts, analyses, and lead scores"
        ))

    def _create_case_types_and_playbooks(self):
        for name, config in DEFAULT_PLAYBOOKS.items():
            case_type, _ = CaseType.objects.get_or_create(
                name=name,
                defaults={"description": config["description"]},
            )
            playbook, _ = Playbook.objects.get_or_create(
                case_type=case_type,
                defaults={
                    "name": f"{name} Intake Playbook",
                    "description": config["description"],
                },
            )
            for i, question_text in enumerate(config["questions"]):
                PlaybookQuestion.objects.get_or_create(
                    playbook=playbook,
                    text=question_text,
                    defaults={"order": i, "is_required": True},
                )

        self.stdout.write(f"  Created {len(DEFAULT_PLAYBOOKS)} case types with playbooks")

    def _load_ground_truth(self) -> dict:
        """Load ground truth indexed by call_id."""
        if not GROUND_TRUTH_PATH.exists():
            self.stdout.write(self.style.WARNING("  No ground_truth.json found"))
            return {}

        with open(GROUND_TRUTH_PATH) as f:
            data = json.load(f)

        # Handle both formats: {"recordings": [...]} or {"call_01": {...}}
        if "recordings" in data:
            return {r["id"]: r["expected"] for r in data["recordings"]}
        return data

    def _load_json(self, filename: str) -> list:
        path = SEED_DIR / filename
        if not path.exists():
            self.stdout.write(self.style.WARNING(f"  {filename} not found, skipping"))
            return []

        with open(path) as f:
            return json.load(f)

    def _create_call(self, call_id, transcript, analysis, scores, ground_truth):
        """Create a Call + Transcript from pipeline data."""
        # Get or match case type
        case_type_name = analysis.get("case_type", "General Inquiry")
        case_type = CaseType.objects.filter(name=case_type_name).first()

        # Compute extraction accuracy vs ground truth
        extraction_accuracy = {}
        if ground_truth:
            extraction_accuracy = {
                "first_name": (
                    analysis.get("first_name", "").lower()
                    == ground_truth.get("first_name", "").lower()
                ),
                "last_name": (
                    analysis.get("last_name", "").lower()
                    == ground_truth.get("last_name", "").lower()
                ),
                "email": (
                    analysis.get("email", "").lower()
                    == ground_truth.get("email", "").lower()
                ),
                "phone": (
                    _normalize_phone(analysis.get("phone", ""))
                    == _normalize_phone(ground_truth.get("phone_number", ""))
                ),
            }

        call, created = Call.objects.update_or_create(
            call_id=call_id,
            defaults={
                "audio_file": f"recordings/{call_id}.wav",
                "duration_seconds": transcript.get("processing_time"),
                "language": transcript.get("language", "de"),
                # Agent 2
                "caller_first_name": analysis.get("first_name", ""),
                "caller_last_name": analysis.get("last_name", ""),
                "caller_email": analysis.get("email", ""),
                "caller_phone": analysis.get("phone", ""),
                "case_type": case_type,
                "urgency": analysis.get("urgency"),
                "key_facts": analysis.get("key_facts", []),
                "summary": analysis.get("summary", ""),
                "resolution_status": analysis.get("resolution_status", "unknown"),
                # Agent 3
                "lead_score": scores.get("lead_score"),
                "lead_score_reasoning": scores.get("lead_score_reasoning", ""),
                "resolution_gaps": scores.get("resolution_gaps", []),
                "playbook_completeness": scores.get("playbook_completeness"),
                "playbook_answered": scores.get("playbook_answered", []),
                "playbook_unanswered": scores.get("playbook_unanswered", []),
                "recommended_actions": scores.get("recommended_actions", []),
                # Quality
                "confidence_scores": analysis.get("confidence_scores", {}),
                "needs_human_review": analysis.get("needs_human_review", False),
                "extraction_accuracy": extraction_accuracy,
            },
        )

        # Create/update transcript
        Transcript.objects.update_or_create(
            call=call,
            defaults={
                "text": transcript.get("text", ""),
                "whisper_model": transcript.get("model", "base"),
                "processing_time_seconds": transcript.get("processing_time"),
            },
        )

        action = "Created" if created else "Updated"
        self.stdout.write(f"  {action} {call_id}")
        return call


def _normalize_phone(phone: str) -> str:
    """Remove spaces and formatting from phone numbers for comparison."""
    return "".join(c for c in phone if c.isdigit() or c == "+")
