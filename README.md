# Marie Phone Dashboard

A legal AI phone assistant dashboard that helps lawyers review calls, track lead conversion, and improve intake quality through AI-powered analysis.

Built as a Product Engineer technical challenge for JUPUS.

## Architecture

The system processes phone call recordings through a three-stage agentic pipeline, then presents results in a dashboard for lawyers.

```
                         ┌─────────────────────────────────────────┐
                         │           Agentic Pipeline              │
                         │                                         │
  ┌──────────┐    ┌──────┴───────┐    ┌──────────────┐    ┌───────┴────────┐
  │  Audio    │───▶│   Agent 1    │───▶│   Agent 2    │───▶│    Agent 3     │
  │  (.wav)   │    │ Transcriber  │    │ Call Analyzer │    │ Lead Intel     │
  └──────────┘    └──────────────┘    └──────────────┘    └────────────────┘
                        │                    │                     │
                   Whisper (local)     Local LLM             Local LLM
                        │                    │                     │
                   transcript          structured data       lead score,
                                       - contact info        resolution status,
                                       - case type           conversion insights
                                       - urgency
                                       - key facts
                                                                  │
                                                                  ▼
                                                    ┌─────────────────────────┐
                                                    │   Django REST API       │
                                                    │   /api/calls/           │
                                                    │   /api/leads/           │
                                                    │   /api/playbooks/       │
                                                    │   /api/insights/        │
                                                    └────────────┬────────────┘
                                                                 │
                                                                 ▼
                                                    ┌─────────────────────────┐
                                                    │   Vue.js Dashboard      │
                                                    │   - Call History        │
                                                    │   - Lead Funnel         │
                                                    │   - Resolution Tracking │
                                                    │   - Playbook Config     │
                                                    └─────────────────────────┘
```

### Agent Details

| Agent | Input | Output | Model | Key Limitation | Mitigation |
|-------|-------|--------|-------|----------------|------------|
| **Transcriber** | WAV audio | Transcript text | Whisper (local) | German legal terminology accuracy | Benchmark against `ground_truth.json`; confidence flagging |
| **Call Analyzer** | Transcript | Structured data (contact, case type, urgency, key facts) | Ollama (local LLM) | Hallucination on contact details (names, emails, phone numbers) | Confidence scores per field; human review flag when low |
| **Lead Intelligence** | Structured call data | Lead score + reasoning, resolution gaps, playbook suggestions | Ollama (local LLM) | Small sample size (30 calls); scoring calibration | Transparent scoring (show reasoning); lawyer can override |

### Why Three Agents Instead of One?

1. **Separation of concerns** — transcription accuracy and legal analysis are fundamentally different problems
2. **Independent testability** — each agent can be evaluated and improved in isolation
3. **Production scalability** — transcription is compute-heavy, analysis is token-heavy; they scale differently
4. **Debuggability** — when output is wrong, you can pinpoint which stage failed

## Killer Feature: Intake Playbook + Resolution Intelligence

### What & Why

Most voice bot dashboards show a flat list of transcripts. Lawyers still have to manually read each one to figure out: *Was this call handled well? Do I need to follow up? Is this a good lead?*

**Intake Playbook + Resolution Intelligence** solves this with two components:

1. **Intake Playbooks** (configurable) — Lawyers define case-type-specific intake requirements (e.g., divorce cases need: parties involved, children, urgency, desired outcome). The system evaluates each call against the relevant playbook to determine completeness.

2. **Resolution Intelligence** (AI-driven) — For every call, the system automatically determines:
   - **Resolution status**: Was the intake complete? Was an appointment booked? Does it need follow-up?
   - **Lead score**: How likely is this caller to convert? (based on urgency, case clarity, engagement)
   - **Conversion funnel**: Visual pipeline from Call → Qualified Lead → Appointment → Client

**Inspired by [Intercom Fin](https://fin.ai/)**: Fin's power isn't the AI itself — it's the configurable Procedures + continuous improvement Flywheel (Train → Test → Deploy → Analyze). We apply the same pattern to legal phone intake.

### Which KPIs & Why

| KPI | How This Feature Drives It |
|-----|---------------------------|
| **Call Resolution Rate** | Playbooks ensure Marie collects complete information per case type. Resolution tracking shows exactly which calls need human follow-up vs. which are fully handled. |
| **Lead Conversion Rate** | Lead scoring + funnel visualization lets lawyers prioritize high-value leads. Insight engine identifies where in the funnel leads drop off and suggests improvements. |

**Why these two KPIs?**
- They are the two metrics that directly translate to **revenue** for law firms: resolved calls = less lawyer time wasted, converted leads = more clients.
- They create a flywheel: better playbooks → higher resolution → more conversions → data to improve playbooks further.

### Validation Plan

| Method | What We Measure | Timeline |
|--------|----------------|----------|
| **A/B test** | Firms with playbooks vs. without → resolution rate delta | 4 weeks |
| **Time-to-action tracking** | Do lawyers act on leads faster with scoring? | 2 weeks |
| **User interviews** | "How do you currently decide which calls to follow up on?" | Week 1 |
| **Funnel drop-off analysis** | Where do leads leak? Does the insight engine's suggestions reduce leakage? | 6 weeks |

## Tech Stack

| Layer | Choice | Rationale |
|-------|--------|-----------|
| Backend | Django + DRF | JUPUS production stack; demonstrates fit |
| Frontend | Vue.js | JUPUS production stack |
| Database | SQLite | POC simplicity; production → PostgreSQL |
| Speech-to-Text | Whisper (openai-whisper, local) | Best open-source ASR; runs locally; multilingual |
| LLM | Ollama + local model | Free, local, no API keys needed |
| Audio processing | ffmpeg / pydub | Standard audio handling |

### Trade-offs

- **SQLite over PostgreSQL**: Faster setup, zero config, single-file DB. Acceptable for 30 calls. Would switch for production (concurrent writes, full-text search, JSON fields).
- **Local LLM over cloud API**: Lower quality than GPT-4/Claude, but meets the "must run locally, free tools only" constraint. Mitigation: structured prompts, confidence scores, human review flags.
- **Monorepo (Django serves Vue build)**: Simpler deployment for POC. Production would separate frontend/backend for independent scaling.

## How to Run

> TODO: Fill in after scaffolding

## Limitations & Future Work

> TODO: Fill in after implementation
