"""
Full pipeline runner: Audio → Transcription → Agent 2 → Quality Gate → Agent 3 → seed data

Per-call processing: each call goes through all stages before the next call starts.
This way, if API quota runs out, you have N complete results instead of N partial.

Pipeline stages per call:
    1. Transcription (Whisper)        — deterministic, not an agent
    2. Agent 2 (Analyzer)             — LLM + Guardrails + Tools + Reflection
    3. Quality Gate (LLM-as-Judge)    — independent audit of Agent 2 output
    4. Agent 3 (Lead Intelligence)    — scoring + playbook evaluation

API key / model rotation (to work within free-tier RPD quotas):
    - Agent 2 + Reflection:  key 1, gemini-2.5-flash-lite
    - Quality Gate:          key 2, gemini-2.5-flash-lite
    - Agent 3:               key 1, gemini-2.5-flash (separate quota)

Usage:
    python -m pipeline.run_pipeline
    python -m pipeline.run_pipeline --skip-transcribe   # reuse existing transcripts
    python -m pipeline.run_pipeline --resume            # retry only failed calls
    python -m pipeline.run_pipeline --no-reflection     # disable reflection loop
    python -m pipeline.run_pipeline --no-quality-gate   # skip quality gate
    python -m pipeline.run_pipeline --limit 5           # process only first N calls
"""

import argparse
import json
import os
import time
from pathlib import Path


ENV_PATH = Path(__file__).parent.parent / ".env"
if ENV_PATH.exists():
    with open(ENV_PATH) as f:
        for line in f:
            line = line.strip()
            if "=" in line and not line.startswith("#"):
                k, v = line.split("=", 1)
                os.environ.setdefault(k, v)


RECORDINGS_DIR = Path(__file__).parent.parent / "data" / "recordings"
SEED_DIR = Path(__file__).parent.parent / "data" / "seed"

# Rate limit pacing (15 RPM = 1 req per 4s)
RATE_LIMIT_DELAY = 4


def _save_all(analyses, audits, scores, analyses_path, quality_path, scores_path):
    """Persist state after each call so partial results are preserved."""
    with open(analyses_path, "w") as f:
        json.dump(analyses, f, indent=2, ensure_ascii=False)
    with open(quality_path, "w") as f:
        json.dump(audits, f, indent=2, ensure_ascii=False)
    with open(scores_path, "w") as f:
        json.dump(scores, f, indent=2, ensure_ascii=False)


def run(
    skip_transcribe: bool = False,
    resume: bool = False,
    enable_reflection: bool = True,
    enable_quality_gate: bool = True,
    limit: int | None = None,
):
    SEED_DIR.mkdir(parents=True, exist_ok=True)

    transcripts_path = SEED_DIR / "transcripts.json"
    analyses_path = SEED_DIR / "analyses.json"
    quality_path = SEED_DIR / "quality_audits.json"
    scores_path = SEED_DIR / "lead_scores.json"

    # --- Transcription Step ---
    if (skip_transcribe or resume) and transcripts_path.exists():
        print("=== Skipping Transcription (using existing transcripts) ===")
        with open(transcripts_path) as f:
            transcripts = json.load(f)
    else:
        print("=== Transcription Step: Whisper ===")
        from pipeline.agent_transcriber import transcribe_batch

        transcripts = transcribe_batch(str(RECORDINGS_DIR))
        with open(transcripts_path, "w") as f:
            json.dump(transcripts, f, indent=2, ensure_ascii=False)
        print(f"  Saved {len(transcripts)} transcripts to {transcripts_path}")

    if limit:
        transcripts = transcripts[:limit]
        print(f"  Limited to first {limit} calls")

    # --- Load cached results (resume mode) ---
    cached_analyses = {}
    cached_audits = {}
    cached_scores = {}
    if resume:
        if analyses_path.exists():
            with open(analyses_path) as f:
                for a in json.load(f):
                    if "error" not in a:
                        cached_analyses[a["call_id"]] = a
        if quality_path.exists():
            with open(quality_path) as f:
                for q in json.load(f):
                    if "error" not in q:
                        cached_audits[q["call_id"]] = q
        if scores_path.exists():
            with open(scores_path) as f:
                for s in json.load(f):
                    if "error" not in s:
                        cached_scores[s["call_id"]] = s
        print(
            f"  Resume: {len(cached_analyses)} analyses, "
            f"{len(cached_audits)} audits, {len(cached_scores)} scores cached"
        )

    # --- Lazy imports so Whisper isn't loaded if skipped ---
    from pipeline.llm_client import set_api_key, set_model
    from pipeline.agent_analyzer import analyze_call
    from pipeline.quality_gate import audit_extraction
    from pipeline.agent_lead_intel import score_lead

    analyses = []
    audits = []
    scores = []

    completed = 0
    failed = 0

    print("\n=== Per-call pipeline processing ===\n")

    for i, t in enumerate(transcripts, 1):
        call_id = t["call_id"]
        transcript_text = t["text"]
        print(f"[{i}/{len(transcripts)}] {call_id}")

        # ---- Stage 1: Agent 2 (Analyzer) ----
        if call_id in cached_analyses:
            print(f"  Agent 2: cached")
            analysis = cached_analyses[call_id]
        else:
            set_api_key(1)
            set_model("gemini-2.5-flash-lite")
            print(f"  Agent 2: analyzing...", end=" ", flush=True)
            try:
                analysis = analyze_call(transcript_text, enable_reflection=enable_reflection)
                analysis["call_id"] = call_id
                reflected = " (reflected)" if analysis.get("reflection_applied") else ""
                print(f"done{reflected}")
            except Exception as e:
                print(f"FAILED: {e}")
                analysis = {"call_id": call_id, "error": str(e), "needs_human_review": True}
                analyses.append(analysis)
                failed += 1
                _save_all(analyses, audits, scores, analyses_path, quality_path, scores_path)
                print(f"  → Stopping pipeline for this call, moving on.\n")
                time.sleep(RATE_LIMIT_DELAY)
                continue
            time.sleep(RATE_LIMIT_DELAY)
            if analysis.get("reflection_applied"):
                time.sleep(RATE_LIMIT_DELAY)

        analyses.append(analysis)

        # ---- Stage 2: Quality Gate ----
        audit = None
        if enable_quality_gate:
            if call_id in cached_audits:
                print(f"  Quality Gate: cached")
                audit = cached_audits[call_id]
            else:
                set_api_key(2)
                set_model("gemini-2.5-flash-lite")
                print(f"  Quality Gate: auditing...", end=" ", flush=True)
                try:
                    audit = audit_extraction(transcript_text, analysis)
                    audit["call_id"] = call_id
                    print(f"done (verdict: {audit['verdict']}, quality: {audit['quality_score']}/5)")
                except Exception as e:
                    print(f"FAILED: {e}")
                    audit = {"call_id": call_id, "error": str(e), "verdict": "review"}
                time.sleep(RATE_LIMIT_DELAY)

            audits.append(audit)

            # Merge audit verdict into analysis
            if audit and "error" not in audit:
                analysis["quality_audit"] = {
                    "quality_score": audit.get("quality_score"),
                    "verdict": audit.get("verdict"),
                    "issues": audit.get("issues", []),
                    "hallucinated_fields": audit.get("hallucinated_fields", []),
                }
                if audit.get("verdict") in ("review", "reject"):
                    analysis["needs_human_review"] = True

        # ---- Stage 3: Agent 3 (Lead Intelligence) ----
        if call_id in cached_scores:
            print(f"  Agent 3: cached")
            score = cached_scores[call_id]
        else:
            set_api_key(1)
            set_model("gemini-2.5-flash")
            print(f"  Agent 3: scoring...", end=" ", flush=True)
            try:
                score = score_lead(analysis)
                score["call_id"] = call_id
                print(f"done (score: {score['lead_score']})")
            except Exception as e:
                print(f"FAILED: {e}")
                score = {"call_id": call_id, "error": str(e), "lead_score": 0}
            time.sleep(RATE_LIMIT_DELAY)

        scores.append(score)

        # Persist after every call so partial results survive rate limit failures
        _save_all(analyses, audits, scores, analyses_path, quality_path, scores_path)

        if "error" not in analysis and (not audit or "error" not in audit) and "error" not in score:
            completed += 1
        else:
            failed += 1

        print()

    # --- Summary ---
    successful_analyses = sum(1 for a in analyses if "error" not in a)
    successful_audits = sum(1 for q in audits if "error" not in q)
    successful_scores = sum(1 for s in scores if "error" not in s)
    reflected_count = sum(1 for a in analyses if a.get("reflection_applied"))

    print("=== Pipeline Complete ===")
    print(f"  Transcripts:  {len(transcripts)}")
    print(f"  Analyses:     {successful_analyses}/{len(analyses)} ({reflected_count} reflected)")
    if enable_quality_gate:
        accept = sum(1 for q in audits if q.get("verdict") == "accept")
        review = sum(1 for q in audits if q.get("verdict") == "review")
        reject = sum(1 for q in audits if q.get("verdict") == "reject")
        print(f"  Quality Gate: {successful_audits}/{len(audits)} (accept={accept}, review={review}, reject={reject})")
    print(f"  Lead scores:  {successful_scores}/{len(scores)}")
    print(f"  Complete pipelines: {completed}/{len(transcripts)}")
    print(f"  Seed data:    {SEED_DIR}/")

    if failed > 0:
        print(f"\n  {failed} calls had failures. Run with --resume to retry only failed calls.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run the full analysis pipeline")
    parser.add_argument("--skip-transcribe", action="store_true",
                        help="Skip Whisper transcription, reuse existing transcripts.json")
    parser.add_argument("--resume", action="store_true",
                        help="Retry only failed calls, keep successful results")
    parser.add_argument("--no-reflection", action="store_true",
                        help="Disable Agent 2 reflection loop")
    parser.add_argument("--no-quality-gate", action="store_true",
                        help="Skip quality gate (LLM-as-Judge) step")
    parser.add_argument("--limit", type=int, default=None,
                        help="Process only the first N calls")
    args = parser.parse_args()

    run(
        skip_transcribe=args.skip_transcribe,
        resume=args.resume,
        enable_reflection=not args.no_reflection,
        enable_quality_gate=not args.no_quality_gate,
        limit=args.limit,
    )
