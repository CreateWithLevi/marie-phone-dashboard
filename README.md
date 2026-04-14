# Marie Phone Dashboard

An AI-powered dashboard for law firms to review, score, and act on phone intake calls. Built as a Product Engineer challenge for JUPUS.

**The problem:** Lawyers using an AI phone assistant (Marie) receive raw transcripts and contact info. They still manually read each transcript to decide: *Is this a good lead? Was the intake complete? What do I need to follow up on?*

**The solution:** A three-agent pipeline that transforms audio recordings into structured, actionable intelligence — with configurable intake playbooks that create a continuous improvement loop.

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

### Agentic Pipeline

```
  ┌──────────┐    ┌──────────────┐    ┌──────────────┐    ┌────────────────┐
  │  Audio   │───▶│   Agent 1    │───▶│   Agent 2    │───▶│    Agent 3     │
  │  (.wav)  │    │ Transcriber  │    │ Call Analyzer │    │ Lead Intel     │
  └──────────┘    └──────────────┘    └──────────────┘    └────────────────┘
                        │                    │                     │
                   Whisper (local)      LLM (multi-           LLM (multi-
                        │               backend)               backend)
                        ▼                    ▼                     ▼
                   transcript          contact info,         lead score +
                                       case type,            reasoning,
                                       urgency,              playbook
                                       key facts,            completeness,
                                       confidence            resolution gaps,
                                       scores                actions
```

| Agent | Input | Output | Key Limitation | Mitigation |
|-------|-------|--------|----------------|------------|
| **1: Transcriber** | WAV audio | Transcript text | German legal terminology; spoken email/phone accuracy | Benchmark vs `ground_truth.json`; confidence flagging |
| **2: Call Analyzer** | Transcript | Structured data (contact, case type, urgency, key facts) | LLM hallucination on contact details | Per-field confidence scores; auto human review flag when confidence < 0.6 |
| **3: Lead Intelligence** | Structured data + playbook questions | Lead score, resolution gaps, playbook completeness, recommended actions | Small sample (30 calls); no calibration data | Transparent reasoning; lawyer override; configurable playbooks |

**Why three agents instead of one?**
1. **Separation of concerns** — transcription accuracy and legal analysis are different problems
2. **Independent testability** — each agent can be evaluated and improved in isolation
3. **Production scalability** — transcription is compute-heavy, analysis is token-heavy
4. **Debuggability** — when output is wrong, you can pinpoint which stage failed

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
Full transcript, contact info with per-field confidence scores and extraction accuracy indicators, lead score with reasoning, case details, playbook coverage (answered/unanswered questions with progress bar), resolution gaps, and recommended actions.

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

The low email accuracy **validates the design** — this is exactly why we built confidence scoring and human review flags. Production improvements: post-processing rules for letter-by-letter spelling, custom Whisper fine-tuning.

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
│   ├── agent_transcriber.py        # Agent 1: Whisper
│   ├── agent_analyzer.py           # Agent 2: Structured extraction
│   ├── agent_lead_intel.py         # Agent 3: Lead scoring + playbook eval
│   ├── llm_client.py               # Multi-backend LLM client
│   ├── run_pipeline.py             # Pipeline runner with resume
│   └── prompts/                    # LLM prompt templates
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
