"""
LLM client with multi-backend support.

Backends (selected via LLM_BACKEND env var):
- "gemini"  : Google Gemini API (free tier, default for dev)
- "ollama"  : Local Ollama server (for reviewers without API keys)

Usage:
    from pipeline.llm_client import llm_generate
    result = llm_generate("Extract the caller's name from: ...")
"""

import json
import os
import time

import requests


LLM_BACKEND = os.environ.get("LLM_BACKEND", "gemini")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.0-flash")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "llama3.2")
OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434")


def llm_generate(prompt: str, system: str = "", json_mode: bool = False) -> str:
    """Send a prompt to the configured LLM backend and return the response text.

    Args:
        prompt: The user prompt
        system: Optional system prompt
        json_mode: If True, request JSON output format

    Returns:
        Response text from the LLM
    """
    backend = LLM_BACKEND.lower()
    if backend == "gemini":
        return _gemini_generate(prompt, system, json_mode)
    elif backend == "ollama":
        return _ollama_generate(prompt, system, json_mode)
    else:
        raise ValueError(f"Unknown LLM_BACKEND: {backend}. Use 'gemini' or 'ollama'.")


def _gemini_generate(prompt: str, system: str, json_mode: bool) -> str:
    """Call Google Gemini API."""
    if not GEMINI_API_KEY:
        raise ValueError(
            "GEMINI_API_KEY not set. Either set it or use LLM_BACKEND=ollama"
        )

    url = (
        f"https://generativelanguage.googleapis.com/v1beta/models/"
        f"{GEMINI_MODEL}:generateContent?key={GEMINI_API_KEY}"
    )

    contents = []
    if system:
        contents.append({"role": "user", "parts": [{"text": system}]})
        contents.append({"role": "model", "parts": [{"text": "Understood."}]})
    contents.append({"role": "user", "parts": [{"text": prompt}]})

    body = {"contents": contents}

    if json_mode:
        body["generationConfig"] = {
            "responseMimeType": "application/json",
        }

    resp = requests.post(url, json=body, timeout=60)
    resp.raise_for_status()

    data = resp.json()
    return data["candidates"][0]["content"]["parts"][0]["text"]


def _ollama_generate(prompt: str, system: str, json_mode: bool) -> str:
    """Call local Ollama server."""
    url = f"{OLLAMA_URL}/api/generate"

    body = {
        "model": OLLAMA_MODEL,
        "prompt": prompt,
        "stream": False,
    }
    if system:
        body["system"] = system
    if json_mode:
        body["format"] = "json"

    try:
        resp = requests.post(url, json=body, timeout=120)
        resp.raise_for_status()
    except requests.ConnectionError:
        raise ConnectionError(
            f"Cannot connect to Ollama at {OLLAMA_URL}. "
            "Start it with 'ollama serve' or use LLM_BACKEND=gemini"
        )

    data = resp.json()
    return data["response"]


def llm_generate_json(prompt: str, system: str = "") -> dict:
    """Generate and parse a JSON response from the LLM.

    Returns parsed dict. Raises ValueError if response is not valid JSON.
    """
    raw = llm_generate(prompt, system, json_mode=True)

    # Clean up potential markdown fences
    text = raw.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[-1]
    if text.endswith("```"):
        text = text.rsplit("```", 1)[0]
    text = text.strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        raise ValueError(f"LLM returned invalid JSON: {e}\nRaw response:\n{raw}")
