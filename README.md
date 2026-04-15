# Marie Phone Dashboard

An AI-powered dashboard for law firms to review, score, and act on phone intake calls. Built as a Product Engineer challenge for JUPUS.

**The problem:** Lawyers using an AI phone assistant (Marie) receive raw transcripts and contact info. They still manually read each transcript to decide: *Is this a good lead? Was the intake complete? What do I need to follow up on?*

**The solution:** A production-minded pipeline that transforms audio recordings into structured, actionable intelligence — with configurable intake playbooks that create a continuous improvement loop. The **Analyzer Agent** is wired with four patterns from modern LLM engineering: **Guardrails**, **Tool Calling**, **Reflection**, and **LLM-as-Judge**.

## Quick Start

```bash
# Prerequisites: Python 3.11+, Node.js 18+, uv (Python package manager)

git clone <repo-url> && cd marie-phone-dashboard

make setup    # Install deps, build frontend, migrate DB
make seed     # Load pre-processed data for all 30 calls
make run      # Start at http://localhost:8000
```

> **Note:** Audio recordings are not included in the repo (they were provided separately). The seed data contains pre-processed pipeline outputs, so Whisper and LLM access are **not required** to run the dashboard.

### Development mode

```bash
make dev      # Django (8000) + Vite HMR (5173)
make test     # Run unit tests for the deterministic layer
```

### Running the pipeline from scratch

```bash
# Place recordings in data/recordings/
# Set environment variables in .env:
#   LLM_BACKEND=gemini (or ollama)
#   GEMINI_API_KEY=your-key
#   GEMINI_MODEL=gemini-2.5-flash-lite

make pipeline          # Run full pipeline (transcribe + analyze + score)
make pipeline-resume   # Resume from last checkpoint (retry failures only)
```

## Architecture

### Pipeline Overview

```
  ┌──────────┐   ┌──────────────┐   ┌──────────────────┐   ┌────────────────┐
  │  Audio   │──▶│ Transcription│──▶│  Analyzer Agent  │──▶│ Lead Intel     │
  │  (.wav)  │   │ Step (Whisper)│  │  (4 patterns)    │   │ Agent          │
  └──────────┘   └──────────────┘   └──────────────────┘   └────────────────┘
                        │                    │                     │
                   deterministic     Guardrails → LLM →        LLM scoring
                   speech-to-text    Tools → Reflection →      vs. playbook
                        │            LLM-as-Judge                   │
                        ▼                    ▼                     ▼
                   transcript          contact, case type,    lead score +
                                       urgency, key facts,    reasoning,
                                       per-field confidence,  playbook
                                       tool corrections,      completeness,
                                       quality audit verdict  gaps, actions
```

| Stage | Kind | Input | Output | Key Limitation | Mitigation |
|-------|------|-------|--------|----------------|------------|
| **Transcription Step** | Deterministic (Whisper) | WAV audio | Transcript text | German legal terms; spoken email/phone accuracy | Benchmark vs `ground_truth.json`; downstream confidence flagging |
| **Analyzer Agent** | LLM + tools + reflection + judge | Transcript | Contact, case type, urgency, key facts, confidence, tool corrections, quality audit | LLM hallucination; overconfident self-assessment | See "Four Patterns in the Analyzer Agent" below |
| **Lead Intel Agent** | LLM + playbook context | Analyzer output + playbook questions | Lead score, resolution gaps, playbook completeness, recommended actions | Small sample (30 calls); no calibration data | Transparent reasoning; lawyer override; configurable playbooks |

**Honest naming:** Whisper is a deterministic speech-to-text model, not an agent — it doesn't decide anything. We call the LLM stages "agents" because they make judgment calls (what to extract, when to re-extract, when to flag). Conflating the two would be marketing, not engineering.

**Why split the LLM work across multiple stages instead of one big prompt?**
1. **Scoped responsibility** — the Analyzer extracts structured fields, the Judge audits the extraction, the Lead Intel agent scores against the playbook. Each prompt is small and targeted.
2. **Debuggability** — when output is wrong you can trace exactly where it broke: Whisper mishearing, Analyzer hallucinating, Tools over-correcting, or Judge being too lenient. A monolithic prompt flattens all of that into one black box.
3. **Independent testability** — each stage can be evaluated and iterated on in isolation, with its own failure modes and its own quality signal.

### Four Patterns in the Analyzer Agent

A naive version of this pipeline would be a single LLM call — transcript in, JSON out. That's sequential, not agentic. The Analyzer Agent is wired with four production patterns (numbered against *Generative AI Design Patterns*):

| Pattern | # | What it does | Where to find it |
|---------|---|--------------|------------------|
| **Guardrails** | 32 | Clamps transcript length, regex-detects prompt injection (`ignore previous instructions`, `</system>`, etc.) before the LLM ever sees it | `pipeline/guardrails.py` |
| **Tool Calling** | 21 | Deterministic email validator (regex + domain typo correction + `"at"→@` reconstruction) and E.164 phone formatter. Tools **auto-lower** the LLM's self-reported confidence when they find invalid data, giving Reflection a chance to fire | `pipeline/tools.py` |
| **Reflection** | 18 | When `first_name`/`last_name`/`email`/`phone` confidence falls below 0.6, re-extracts with a focused prompt that hints at NATO/German spelling alphabet. Only adopts the new result if it's more confident than the first pass | `pipeline/agent_analyzer.py`, `prompts/reflection.txt` |
| **LLM-as-Judge** | 17 | A second, independent LLM call audits the Analyzer's output for faithfulness, completeness, and accuracy. Different prompt, fresh context, optionally a different model. Returns `accept` / `review` / `reject` + a 1–5 quality score. `review` or `reject` auto-trips `needs_human_review` | `pipeline/quality_gate.py`, `prompts/quality_gate.txt` |

**Why LLM-as-Judge is a separate LLM call:** self-evaluation in a single pass is peer pressure with one peer — the model defends what it just produced. Splitting it into a second call with a fresh context and an audit-framed prompt makes the Judge re-read the transcript independently, without inheriting the Analyzer's reasoning chain. The two calls can also use different models (e.g. Analyzer on `gemini-2.5-flash`, Judge on `flash-lite`) for ensemble-style cross-checking.

**A note on the dual API key setup:** this codebase happens to run Analyzer and Judge on separate Gemini API keys, but that's a pragmatic free-tier workaround for rate-limit isolation (so exhausting one quota doesn't block the other), not a requirement of the pattern. In a paid environment a single key works fine — what matters is the independent call, not the independent credential.

**Per-call execution:** The pipeline processes each call through all stages before moving to the next, rather than running all Analyzer calls first and all Lead Intel calls second. If the API quota runs out mid-run, you have N complete results instead of N partial stages. `--resume` retries only the failures.

### LLM Backend

The pipeline supports multiple backends via environment variables:
- **Gemini API** (default) — free tier with rate limit management (dual API key rotation, per-model RPD quotas, resume capability)
- **Ollama** — local inference, no API keys needed

This is a pragmatic choice: develop with Gemini for speed, deploy with Ollama for zero external dependencies.

## Killer Feature: Intake Playbook + Resolution Intelligence

### What & Why

Inspired by [Intercom Fin](https://fin.ai/) — Fin's power isn't the AI itself, it's the configurable **Procedures** and continuous improvement **Flywheel**.

**Two components:**

1. **Intake Playbooks** (configurable) — Lawyers define case-type-specific intake requirements (e.g., divorce: children involved? existing court orders? desired outcome?). Every call is evaluated against the relevant playbook.

2. **Resolution Intelligence** (AI-driven) — Each call gets: lead score with reasoning, resolution status, playbook completeness %, specific gaps, and recommended next actions.

**The Flywheel:**
```
Lawyer defines playbook questions
    → AI evaluates each call's completeness
    → Dashboard shows which questions are frequently unanswered
    → Lawyer adjusts playbook
    → Next intake cycle is more complete
```

### KPIs

| KPI | How This Feature Drives It |
|-----|---------------------------|
| **Call Resolution Rate** | Playbooks ensure complete intake per case type. Resolution tracking shows which calls need follow-up vs. fully handled. |
| **Lead Conversion Rate** | Lead scoring + funnel visualization lets lawyers prioritize high-value leads. Resolution gaps identify where leads drop off. |

### Validation Plan

| Method | What We Measure | Timeline |
|--------|----------------|----------|
| User interviews | "How do you currently decide which calls to follow up on?" | Week 1 |
| Time-to-action tracking | Do lawyers act on leads faster with scoring? | 2 weeks |
| A/B test | Firms with playbooks vs. without → resolution rate delta | 4 weeks |
| Funnel drop-off analysis | Where do leads leak? Do suggested actions reduce leakage? | 6 weeks |

## Dashboard Views

### Dashboard
KPI cards (total calls, avg lead score, avg urgency, needs review) + resolution funnel + case type breakdown + lead quality distribution.

### Call List
Filterable and sortable table. Filter by resolution status, sort by lead score or urgency. Search across caller name, email, and summary.

### Call Detail
Full transcript, contact info with per-field confidence scores and extraction accuracy indicators, lead score with reasoning, case details, playbook coverage (answered/unanswered questions with progress bar), resolution gaps, and recommended actions. Also surfaces the Analyzer Agent's agentic metadata: a **Quality Audit card** (Judge verdict + score + issues + hallucinated fields), a **Tool Corrections card** (what the deterministic tools fixed), and a **Reflected badge** in the header when the Reflection loop fired.

### Playbook Editor
Expandable cards per case type. Inline click-to-edit questions, add new questions, remove questions. Required/optional indicators.

## API Endpoints

| Method | Endpoint | Purpose |
|--------|----------|---------|
| GET | `/api/calls/` | List calls (filter, sort, search) |
| GET | `/api/calls/:id/` | Call detail with transcript + analysis |
| GET | `/api/dashboard/stats/` | Aggregated KPIs + funnel |
| GET | `/api/playbooks/` | Playbook list with questions |
| POST | `/api/playbooks/:id/add_question/` | Add intake question |
| PATCH | `/api/playbooks/:id/update_question/:qid/` | Edit question text |
| DELETE | `/api/playbooks/:id/remove_question/:qid/` | Remove question |
| GET | `/api/evaluation/` | Ground truth accuracy report |

## Tech Stack

| Layer | Choice | Rationale |
|-------|--------|-----------|
| Backend | Django + DRF | JUPUS production stack |
| Frontend | Vue.js 3 + Vite | JUPUS production stack |
| Styling | Tailwind CSS | Utility-first, no component library overhead |
| Database | SQLite | Zero config for POC; production → PostgreSQL |
| Speech-to-Text | Whisper (openai-whisper) | Best open-source ASR; local; multilingual |
| LLM | Gemini API / Ollama | Multi-backend: free API for dev, local for production |

## Extraction Accuracy

Evaluated against `ground_truth.json` (30 calls):

| Field | Accuracy | Analysis |
|-------|----------|----------|
| First name | 80.0% | Common German names OK; foreign names often misheard by Whisper |
| Last name | 76.7% | Similar pattern to first name |
| Email | 36.7% | Expected — callers spell email letter-by-letter, Whisper frequently mishears |
| Phone | 76.7% | Digits correct but formatting inconsistent |

The low email accuracy **validates the design** — this is exactly why we built Tool Calling (domain typo correction, `"at"→@` reconstruction), confidence scoring, and the Quality Gate. Production improvements: post-processing rules for letter-by-letter spelling, custom Whisper fine-tuning.

### Quality Gate results (30 calls)

| Verdict | Count | What it means |
|---------|-------|---------------|
| `accept` | 13 | Judge found the extraction faithful, complete, and accurate |
| `review` | 17 | Judge flagged something a human should verify (often Tool-applied corrections that deviate from the raw transcript) |
| `reject` | 0 | No outright hallucinations detected |

**Reflection triggered:** 0/30. Tools fixed most low-confidence cases before Reflection needed to fire — Reflection is the safety net, not the workhorse. The pattern is wired in and tested, ready to catch cases tools can't resolve.

## Testing

**134 tests** cover the **deterministic layer** — the parts of the pipeline where behavior is fully specified and testable in isolation. Full suite runs in under 0.2s:

```bash
make test
```

| Test file | Tests | Coverage |
|-----------|-------|----------|
| `tests/test_tools.py` | 49 | Email validation (8 domain typos parametrized, German spoken-at variants `at`/`ett`/`ätt`, trailing dot, whitespace, lowercase), phone E.164 normalization (4 separator styles, `0049`/`49`/`+49` prefixes), contact completeness grading, `apply_tools()` confidence-lowering contract (never raises confidence, handles missing `confidence_scores` key) |
| `tests/test_guardrails.py` | 28 | `sanitize_transcript()` empty/whitespace handling, **every one of the 7 `INJECTION_PATTERNS` parametrized with a covering example**, case-insensitivity, exact-boundary length clamp at `MAX_TRANSCRIPT_LENGTH`, short-transcript warning. `validate_agent_output()` missing-field reporting (single + multi), `None` vs empty-string semantics, suspiciously-long-string warning without invalidating output |
| `tests/test_analyzer_helpers.py` | 57 | `_normalize()` schema enforcement: **all 8 `VALID_CASE_TYPES` parametrized**, all 4 `VALID_RESOLUTION_STATUSES` parametrized, urgency clamping (over/under/zero/float/numeric string/garbage), `key_facts` coerced to list, `confidence_scores` clamping + numeric-string coercion + non-dict fallback, string-field whitespace stripping |

**What's intentionally not unit-tested:** the LLM stages (`analyze_call`, `audit_extraction`, `score_lead`). Mocking an LLM in a unit test just tests your mock. Those stages are validated via:
- **LLM-as-Judge Quality Gate** — every extraction is audited against the transcript
- **Ground-truth evaluation** — `extraction_accuracy` computed on every seed load is effectively a regression test

This is a deliberate trade-off: test contracts that have truth values, evaluate behaviors that have distributions.

## Limitations

- **No real-time pipeline** — calls are batch-processed, not triggered on ingest. Production would add a webhook/queue trigger.
- **No authentication** — POC assumes single-tenant. Production needs firm-level auth + RBAC.
- **SQLite** — no concurrent write support. Production → PostgreSQL.
- **LLM confidence calibration** — LLMs tend to be overconfident. 30 calls is insufficient to calibrate scoring. Production needs a feedback loop (lawyer confirms/corrects → retrain).
- **No audio playback** — dashboard shows transcript but cannot play the original recording.
- **Playbook changes don't retroactively re-score** — editing a playbook updates future evaluations, not past calls. Production would offer a re-run option.

## Project Structure

```
marie-phone-dashboard/
├── README.md
├── DESIGN.md                       # Intercom-inspired design system
├── Makefile                        # make setup / seed / run / dev / pipeline
├── pyproject.toml
├── manage.py
├── data/
│   ├── ground_truth.json           # Contact info ground truth (provided)
│   ├── recordings/                 # WAV files (gitignored, provided separately)
│   └── seed/                       # Pre-processed pipeline outputs (committed)
├── server/                         # Django project config
├── calls/                          # Django app: models, API, management commands
│   ├── models.py                   # Call, Transcript, CaseType, Playbook
│   ├── serializers.py              # List vs Detail serializers
│   ├── views.py                    # ViewSets + dashboard stats + evaluation
│   └── management/commands/
│       └── seed_data.py            # Load seed data + compute accuracy
├── pipeline/                       # Agentic pipeline (standalone)
│   ├── agent_transcriber.py        # Transcription Step (Whisper, deterministic)
│   ├── agent_analyzer.py           # Analyzer Agent (4 patterns wired in)
│   ├── agent_lead_intel.py         # Lead Intel Agent (scoring + playbook eval)
│   ├── guardrails.py               # Pattern #32: input sanitization
│   ├── tools.py                    # Pattern #21: email/phone validators
│   ├── quality_gate.py             # Pattern #17: LLM-as-Judge audit
│   ├── llm_client.py               # Multi-backend LLM client (key/model rotation)
│   ├── run_pipeline.py             # Per-call pipeline runner with --resume
│   └── prompts/                    # LLM prompt templates (analyze/reflection/judge)
└── frontend/                       # Vue.js 3 + Vite + Tailwind
    └── src/
        ├── App.vue                 # Sidebar layout
        ├── api.js                  # Axios API client
        ├── router.js
        ├── style.css               # Design tokens + Tailwind config
        └── views/
            ├── DashboardView.vue
            ├── CallListView.vue
            ├── CallDetailView.vue
            └── PlaybookView.vue
```

## Development Log

See [docs/DEVLOG.md](docs/DEVLOG.md) for the full engineering decision log — every architectural choice, trade-off, and lesson learned during development.
