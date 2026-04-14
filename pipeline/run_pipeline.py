"""
Full pipeline runner: Audio → Agent 1 → Agent 2 → Agent 3 → seed data

Outputs JSON files to data/seed/ for loading into Django without
requiring Whisper or LLM at review time.

Usage:
    python -m pipeline.run_pipeline
    python -m pipeline.run_pipeline --skip-transcribe  # reuse existing transcripts
    python -m pipeline.run_pipeline --resume            # retry only failed calls
"""

import argparse
import json
import os
import time
from pathlib import Path


# Load .env if present
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


def run(skip_transcribe: bool = False, resume: bool = False):
    SEED_DIR.mkdir(parents=True, exist_ok=True)

    transcripts_path = SEED_DIR / "transcripts.json"
    analyses_path = SEED_DIR / "analyses.json"
    scores_path = SEED_DIR / "lead_scores.json"

    # --- Agent 1: Transcribe ---
    if (skip_transcribe or resume) and transcripts_path.exists():
        print("=== Skipping Agent 1 (using existing transcripts) ===")
        with open(transcripts_path) as f:
            transcripts = json.load(f)
    else:
        print("=== Agent 1: Transcribing all calls ===")
        from pipeline.agent_transcriber import transcribe_batch

        transcripts = transcribe_batch(str(RECORDINGS_DIR))
        with open(transcripts_path, "w") as f:
            json.dump(transcripts, f, indent=2, ensure_ascii=False)
        print(f"  Saved {len(transcripts)} transcripts to {transcripts_path}")

    # --- Load existing results for resume mode ---
    existing_analyses = {}
    existing_scores = {}
    if resume:
        if analyses_path.exists():
            with open(analyses_path) as f:
                for a in json.load(f):
                    if "error" not in a:
                        existing_analyses[a["call_id"]] = a
        if scores_path.exists():
            with open(scores_path) as f:
                for s in json.load(f):
                    if "error" not in s:
                        existing_scores[s["call_id"]] = s
        print(f"  Resuming: {len(existing_analyses)} analyses, {len(existing_scores)} scores already done")

    # --- Agent 2: Analyze (uses API key 1) ---
    print("\n=== Agent 2: Analyzing all calls ===")
    from pipeline.llm_client import set_api_key
    set_api_key(1)
    from pipeline.agent_analyzer import analyze_call

    analyses = []
    for t in transcripts:
        call_id = t["call_id"]

        if call_id in existing_analyses:
            print(f"  {call_id}: cached")
            analyses.append(existing_analyses[call_id])
            continue

        print(f"  Analyzing {call_id}...", end=" ", flush=True)

        try:
            result = analyze_call(t["text"])
            result["call_id"] = call_id
            analyses.append(result)
            print("done")
        except Exception as e:
            print(f"error: {e}")
            analyses.append({"call_id": call_id, "error": str(e)})

        # Respect rate limits (15 RPM = 1 req per 4s)
        time.sleep(4)

    with open(analyses_path, "w") as f:
        json.dump(analyses, f, indent=2, ensure_ascii=False)
    successful_analyses = sum(1 for a in analyses if "error" not in a)
    print(f"  Saved {len(analyses)} analyses ({successful_analyses} successful)")

    # --- Agent 3: Lead Intelligence (uses API key 2) ---
    set_api_key(2)
    print("\n=== Agent 3: Scoring all leads ===")
    from pipeline.agent_lead_intel import score_lead

    scores = []
    for a in analyses:
        call_id = a.get("call_id", "unknown")
        if "error" in a:
            print(f"  Skipping {call_id} (analysis failed)")
            continue

        if call_id in existing_scores:
            print(f"  {call_id}: cached")
            scores.append(existing_scores[call_id])
            continue

        print(f"  Scoring {call_id}...", end=" ", flush=True)

        try:
            result = score_lead(a)
            result["call_id"] = call_id
            scores.append(result)
            print(f"done (score: {result['lead_score']})")
        except Exception as e:
            print(f"error: {e}")
            scores.append({"call_id": call_id, "error": str(e), "lead_score": 0})

        # Respect rate limits
        time.sleep(4)

    with open(scores_path, "w") as f:
        json.dump(scores, f, indent=2, ensure_ascii=False)
    successful_scores = sum(1 for s in scores if "error" not in s)
    print(f"  Saved {len(scores)} lead scores ({successful_scores} successful)")

    # --- Summary ---
    print("\n=== Pipeline Complete ===")
    print(f"  Transcripts: {len(transcripts)}")
    print(f"  Analyses:    {successful_analyses}/{len(analyses)}")
    print(f"  Lead scores: {successful_scores}/{len(scores)}")
    print(f"  Seed data:   {SEED_DIR}/")

    if successful_analyses < len(transcripts) or successful_scores < successful_analyses:
        print("\n  Some calls failed. Run with --resume to retry only failed calls.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run the full analysis pipeline")
    parser.add_argument(
        "--skip-transcribe",
        action="store_true",
        help="Skip Whisper transcription, reuse existing transcripts.json",
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Retry only failed calls, keep successful results",
    )
    args = parser.parse_args()
    run(skip_transcribe=args.skip_transcribe, resume=args.resume)
