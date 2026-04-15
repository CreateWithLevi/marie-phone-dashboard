"""
Transcription Step — Whisper speech-to-text (deterministic, not an agent)

This is a deterministic processing step, not an agent. It has no decision-making
capability — it simply converts audio to text using Whisper. The distinction
matters: agents reason and act, this step transforms data.

Input:  Path to WAV audio file
Output: {
    "text": str,           # Full transcript
    "segments": list,      # Timestamped segments
    "language": str,       # Detected language
    "model": str,          # Whisper model used
    "processing_time": float  # Seconds
}

Limitations:
- German legal terminology may be inaccurate (proper nouns, email addresses)
- Email addresses spoken letter-by-letter are often garbled
- CPU-only inference is slow (~14s for 19s audio with 'base' model)

Mitigations:
- Use language='de' hint to improve German accuracy
- Benchmark extracted contact info against ground_truth.json
- Confidence scoring in Agent 2 flags uncertain extractions
"""

import time
from pathlib import Path


def transcribe(audio_path: str, model_name: str = "base") -> dict:
    """Transcribe an audio file using Whisper.

    Args:
        audio_path: Path to WAV file
        model_name: Whisper model size ('tiny', 'base', 'small', 'medium', 'large')
                    base is a good speed/accuracy trade-off for 19s clips

    Returns:
        dict with text, segments, language, model, processing_time
    """
    import whisper

    path = Path(audio_path)
    if not path.exists():
        raise FileNotFoundError(f"Audio file not found: {audio_path}")

    model = _get_model(model_name)

    start = time.time()
    result = model.transcribe(str(path), language="de")
    elapsed = time.time() - start

    return {
        "text": result["text"].strip(),
        "segments": [
            {
                "start": seg["start"],
                "end": seg["end"],
                "text": seg["text"].strip(),
            }
            for seg in result.get("segments", [])
        ],
        "language": result.get("language", "de"),
        "model": model_name,
        "processing_time": round(elapsed, 2),
    }


# Cache loaded models to avoid reloading for each call
_model_cache = {}


def _get_model(model_name: str):
    """Load and cache a Whisper model."""
    if model_name not in _model_cache:
        import whisper
        _model_cache[model_name] = whisper.load_model(model_name)
    return _model_cache[model_name]


def transcribe_batch(audio_dir: str, model_name: str = "base") -> list[dict]:
    """Transcribe all WAV files in a directory.

    Returns list of dicts with call_id + transcription results.
    """
    audio_path = Path(audio_dir)
    wav_files = sorted(audio_path.glob("*.wav"))

    if not wav_files:
        raise FileNotFoundError(f"No WAV files found in {audio_dir}")

    results = []
    for wav_file in wav_files:
        call_id = wav_file.stem  # e.g., "call_01"
        print(f"  Transcribing {call_id}...", end=" ", flush=True)

        result = transcribe(str(wav_file), model_name)
        result["call_id"] = call_id
        results.append(result)

        print(f"done ({result['processing_time']}s)")

    return results
