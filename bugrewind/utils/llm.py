"""
BugRewind LLM Utility.

Provides a thin wrapper around the Ollama local API at
http://localhost:11434/api/generate.  All agent nodes call
``call_ollama()`` to get LLM completions without any cloud dependency.
"""

from __future__ import annotations

import json
import logging
import httpx

logger = logging.getLogger(__name__)

OLLAMA_URL = "https://pvhd9wks-11434.inc1.devtunnels.ms/api/generate"
DEFAULT_MODEL = "kimi-k2.5:cloud"
REQUEST_TIMEOUT = 500.0  # seconds – local LLMs can be slow


def call_ollama(
    prompt: str,
    *,
    model: str = DEFAULT_MODEL,
    temperature: float = 0.2,
    max_tokens: int = 4096,
) -> str:
    """Send a prompt to the local Ollama instance and return the full response.

    Uses the ``/api/generate`` endpoint with ``stream=false`` for simplicity.

    Args:
        prompt:      The full prompt text (system + user context baked in).
        model:       Ollama model tag, e.g. ``"kimi-k2.5:cloud"`` or ``"codellama"``.
        temperature: Sampling temperature.  Lower → more deterministic.
        max_tokens:  Maximum number of tokens to generate.

    Returns:
        The model's generated text as a plain string.

    Raises:
        httpx.HTTPStatusError: If the Ollama API returns a non-2xx status.
        httpx.ConnectError:    If Ollama is not running on localhost:11434.
    """
    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "options": {
            "temperature": temperature,
            "num_predict": max_tokens,
        },
    }

    logger.debug("Calling Ollama model=%s, prompt length=%d chars", model, len(prompt))

    with httpx.Client(timeout=REQUEST_TIMEOUT) as client:
        response = client.post(OLLAMA_URL, json=payload)
        response.raise_for_status()

    data = response.json()
    text: str = data.get("response", "")
    logger.debug("Ollama returned %d chars", len(text))
    return text.strip()


def call_ollama_json(
    prompt: str,
    *,
    model: str = DEFAULT_MODEL,
    temperature: float = 0.1,
) -> dict | list:
    """Call Ollama requesting JSON-mode output and parse the result.

    Ollama supports ``"format": "json"`` which coerces the model to
    produce valid JSON.  We layer a ``json.loads`` on top and fall back
    to returning the raw string wrapped in a dict on parse failure.

    Returns:
        Parsed JSON (dict or list).
    """
    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "format": "json",
        "options": {
            "temperature": temperature,
            "num_predict": 4096,
        },
    }

    logger.debug("Calling Ollama (JSON mode) model=%s", model)

    with httpx.Client(timeout=REQUEST_TIMEOUT) as client:
        response = client.post(OLLAMA_URL, json=payload)
        response.raise_for_status()

    raw = response.json().get("response", "")

    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        logger.warning("Ollama JSON decode failed, returning raw text in wrapper")
        return {"raw": raw}
