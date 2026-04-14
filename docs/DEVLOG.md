# Engineering Decision Log

A chronological record of architectural decisions, trade-offs, and lessons learned during the Marie Phone Dashboard build.

---

## Phase 0: Problem Analysis (Day 1)

### Data Observations
- 30 WAV recordings (mono 44100Hz, ~19s each, 72MB total)
- `ground_truth.json` contains only contact info (name, email, phone) — no case type, urgency, or resolution data
- Recordings are German-language legal intake calls
- The minimal ground truth structure intentionally leaves room to demonstrate what AI can extract beyond basic contact info

### Decision 1: Tech Stack
**Choice:** Django + DRF + Vue.js + SQLite

**Rationale:** Matches JUPUS production stack (Python/Django + Vue.js). SQLite for POC simplicity — production would use PostgreSQL for concurrent writes and full-text search, but for 30 records the setup cost isn't justified.

### Decision 2: Killer Feature Direction

| Direction | Concept | Why Not |
|-----------|---------|---------|
| Smart Lead Scoring | AI scores lead quality | Too generic, not domain-specific |
| Auto Case File Draft | Generate case files from transcript | Interesting but doesn't directly drive KPIs |
| Follow-up Automation | Auto-send emails/SMS after calls | Requires external services, hard to demo |
| **Intake Playbook + Resolution Intelligence** | Configurable intake flows + AI tracking | **Selected** |

**Why Intake Playbook + Resolution Intelligence:**
1. Inspired by Intercom Fin — Fin's power is configurable Procedures + continuous improvement Flywheel, not AI alone
2. Directly drives two revenue KPIs: Call Resolution Rate and Lead Conversion Rate
3. Domain-specific: different legal areas need different intake questions
4. Strong agentic architecture showcase (the challenge explicitly asks to focus on the agentic part)

### Decision 3: Three-Agent Pipeline

**Why three agents instead of one large prompt:**
- Separation of concerns — transcription accuracy and legal analysis are fundamentally different problems
- Independent testability — can evaluate Whisper accuracy separately from LLM extraction quality
- Production scalability — transcription is compute-heavy, analysis is token-heavy
- Debuggability — when a name is wrong, we can trace it to Whisper (Agent 1) vs. LLM hallucination (Agent 2)

---

## Phase 1: Django Scaffold (Day 1)

### Schema Design Decisions

**Q: Why denormalize Call model?**
30 records, dashboard needs all fields in one query. Query simplicity > schema purity. Production would normalize (separate CallAnalysis table with versioning).

**Q: Why is Transcript a separate model?**
Different agent output (Whisper vs LLM), different access pattern (call list doesn't need transcript text). Separation of concerns.

**Q: Why JSONField for confidence_scores, key_facts?**
Flexibility > query efficiency. Only displayed on call detail page, no need for cross-call queries. PostgreSQL JSON operators can solve this limitation in production.

---

## Phase 2a: Agent 1 — Whisper Transcription (Day 1)

### Environment Issues
- PyTorch 2.6+ doesn't support macOS x86_64 — pinned `torch==2.2.2`
- NumPy 2.x incompatible with torch 2.2 — pinned `numpy<2`

### Whisper Model Selection

| Model | Size | Speed (19s clip) | Quality |
|-------|------|-------------------|---------|
| tiny | 39MB | ~3s | More errors |
| **base** | 139MB | ~4-14s | **Acceptable trade-off** |
| small | 461MB | ~30s | Slightly better but 4x slower |
| medium | 1.5GB | ~60s+ | Too slow for POC |

**Choice: `base`** — The accuracy gap between base and small isn't worth 4x processing time. The main errors (name misspellings, garbled emails) aren't solved by a bigger model — they're inherent to speech-to-text on spoken email addresses and foreign names.

### Test Results

| Call | Ground Truth | Whisper | Correct? |
|------|-------------|---------|----------|
| call_01 | Johanna Schmidt | "Jana Schmidt" | Name wrong |
| call_05 | Sandra Weber | "Sandra Weber" | Correct |
| call_26 | Ahmed Hassan | "Arme Tassan" | Completely wrong (foreign name) |

**Key finding:** Name errors come from Whisper, not the LLM. This validates the agent separation — we can trace error source precisely.

---

## Phase 2b: Agent 2 — Call Analyzer (Day 2)

### LLM Backend Design

**Choice:** Multi-backend client (Gemini API + Ollama)

```python
llm_generate(prompt, system, json_mode) → str
llm_generate_json(prompt, system) → dict
```

- Environment variables control backend: `LLM_BACKEND`, `GEMINI_API_KEY`, `GEMINI_MODEL`, `OLLAMA_MODEL`
- Gemini: REST API directly (no SDK — fewer deps, more transparent)
- Ollama: `/api/generate` with `format: json`

### Post-Processing

Two layers after LLM output:
1. **Normalization** — validate case_type against 8 predefined types, clamp urgency 1-5, clamp confidence 0.0-1.0
2. **Review flagging** — any contact field confidence < 0.6 → auto-flag for human review

### Key Findings

- Agent 2 faithfully uses transcript data — name errors propagate from Whisper (correct behavior)
- Email reconstruction is Agent 2's core value — transforms "aggmail.com" → "@gmail.com"
- Case type classification is accurate — correctly interprets German legal terminology
- Confidence scores tend to be overconfident — a known LLM limitation

---

## Phase 2c: Agent 3 — Lead Intelligence (Day 2)

### Design Concept

Agent 3 is the killer feature engine:
```
Agent 2 output (what the caller said)
    + Playbook questions (what the firm needs to know)
    = Lead score + resolution gaps + recommended actions
```

### Default Playbooks
Built-in intake questions for 8 case types (Family Law, Traffic Law, Employment, Landlord-Tenant, Criminal, Immigration, Contract Dispute, General Inquiry). If lawyers don't customize, these defaults provide immediate value.

### Scoring Validation
- call_01 (General Inquiry, minimal info): score 30, playbook 0% — correct (has contact but no case details)
- Calls with complete info + clear case type + urgency: scores 70-90
- Score range across 30 calls: 35-90, reasonable distribution

---

## Phase 2d: Full Pipeline Run (Day 2)

### Gemini Free Tier Rate Limit Management

| Attempt | Model | Result | Lesson |
|---------|-------|--------|--------|
| 1 | gemini-2.0-flash | Quota = 0 | Some free tier models have zero quota |
| 2 | gemini-3.1-flash-lite-preview | Persistent 503 | Preview models are unstable for batch |
| 3 | gemini-2.5-flash-lite | Stable, 20 RPD | Free tier RPD is a hard limit |
| 4 | Two API keys + model rotation | 30/30 complete | Different keys and models have separate RPD |

**Solution:** Dual API key rotation (Agent 2 uses key 1, Agent 3 uses key 2) + `--resume` flag to retry only failed calls + exponential backoff for 429/503 errors.

**Engineering principle:** External API limitations shouldn't dictate your architecture. The agent separation is correct; the rate limit problem is solved at the infrastructure layer.

### Pipeline Results

| Agent | Success | Time |
|-------|---------|------|
| Agent 1 (Whisper) | 30/30 | ~169s total (~5.6s/call on CPU) |
| Agent 2 (Analyzer) | 30/30 | Gemini 2.5 Flash Lite |
| Agent 3 (Lead Intel) | 30/30 | Score range 35-90 |

### Extraction Accuracy vs Ground Truth

| Field | Accuracy | Why |
|-------|----------|-----|
| First name | 80.0% | Common German names OK; foreign names fail (Whisper) |
| Last name | 76.7% | Similar to first name |
| Email | 36.7% | Callers spell letter-by-letter; Whisper frequently mishears |
| Phone | 76.7% | Digits correct but formatting varies |

**The 36.7% email accuracy is not a bug — it validates the design.** This is exactly why confidence scoring and human review flags exist. Production improvements: post-processing for letter-by-letter spelling patterns, custom Whisper fine-tuning.

---

## Phase 3: API + Frontend (Day 2)

### API Design Decisions
- **Two serializers** for Call: list (lightweight, no transcript/reasoning) vs. detail (everything). Reduces payload for the call list view.
- **`select_related` + `prefetch_related`** to avoid N+1 queries. Overkill for 30 records, but demonstrates good habits.
- **Filtering**: case_type, resolution_status, needs_review, urgency_min, full-text search
- **Sorting**: lead_score, urgency, call_id, playbook_completeness

### Flywheel Connection (Decision 9)

The playbook and call views could look like two separate features. The flywheel connection makes them one system:

```
Lawyer defines playbook questions
    → AI evaluates each call's completeness
    → Dashboard shows which questions go unanswered
    → Lawyer adjusts playbook
    → Next intake cycle is more complete
```

In CallDetailView: green checkmarks for answered questions, red X for unanswered, progress bar for completeness. This makes the connection visible.

### Production Deployment (Decision 10)

**Choice:** Django serves Vue build (single process)

Reviewer runs: `make setup && make seed && make run` → one terminal, one URL. No nginx, Docker, or additional infrastructure. Production would use nginx reverse proxy, but POC simplicity > production-readiness.

---

## Phase 4: UI Polish + Inline Editing (Day 2)

### Design System
Applied Intercom Fin's visual language consistently: warm cream (`#faf9f6`) backgrounds, off-black (`#111111`) text, oat (`#dedbd6`) borders, report palette for data visualization badges. See [DESIGN.md](../DESIGN.md).

### Playbook Inline Edit
Chose inline edit over modal because lawyers typically edit one question at a time. Click to edit → auto-focus + select text → Enter to save / Escape to cancel. Minimal friction for a simple data model.
