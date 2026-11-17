"""
Vectra LLM Utility.

Provides a thin wrapper around the Ollama local API at
http://localhost:11434/api/generate.  All agent nodes call
``call_ollama()`` to get LLM completions without any cloud dependency.

Includes automatic retry with exponential back-off for transient errors
(502, 503, 504, connection resets, timeouts).
"""

from __future__ import annotations

import json
import logging
import time
import httpx

from vectra.config import OLLAMA_URL, DEFAULT_MODEL, LLM_TIMEOUT

logger = logging.getLogger(__name__)

REQUEST_TIMEOUT = LLM_TIMEOUT  # seconds – local LLMs can be slow

# Retry configuration
MAX_RETRIES = 3
RETRY_BACKOFF_BASE = 10  # seconds — first retry waits 10s, then 20s, then 40s
RETRYABLE_STATUS_CODES = {502, 503, 504}


def _is_retryable(exc: Exception) -> bool:
    """Check if an exception is transient and worth retrying."""
    if isinstance(exc, httpx.HTTPStatusError):
        return exc.response.status_code in RETRYABLE_STATUS_CODES
    if isinstance(exc, (httpx.ConnectError, httpx.ReadTimeout, httpx.WriteTimeout,
                        httpx.PoolTimeout, httpx.ConnectTimeout)):
        return True
    return False


def call_ollama(
    prompt: str,
    *,
    model: str = DEFAULT_MODEL,
    temperature: float = 0.2,
    max_tokens: int = 4096,
    json_mode: bool = False,
) -> str:
    """Send a prompt to the local Ollama instance and return the full response.

    Uses the ``/api/generate`` endpoint with ``stream=false`` for simplicity.
    Retries up to ``MAX_RETRIES`` times on transient failures (502/503/504,
    connection errors, timeouts).

    Args:
        prompt:      The full prompt text (system + user context baked in).
        model:       Ollama model tag, e.g. ``"qwen3-coder-next:cloud"`` or ``"codellama"``.
        temperature: Sampling temperature.  Lower → more deterministic.
        max_tokens:  Maximum number of tokens to generate.
        json_mode:   If True, forces the response to be valid JSON.

    Returns:
        The model's generated text as a plain string.

    Raises:
        httpx.HTTPStatusError: If the Ollama API returns a non-2xx status
                               after all retries are exhausted.
        httpx.ConnectError:    If Ollama is unreachable after all retries.
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
    if json_mode:
        payload["format"] = "json"

    logger.debug("Calling Ollama model=%s, prompt length=%d chars", model, len(prompt))

    last_exc: Exception | None = None

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            with httpx.Client(timeout=REQUEST_TIMEOUT) as client:
                response = client.post(OLLAMA_URL, json=payload)
                response.raise_for_status()

            data = response.json()
            text: str = data.get("response", "")
            logger.debug("Ollama returned %d chars", len(text))
            return text.strip()

        except Exception as exc:
            last_exc = exc
            if not _is_retryable(exc) or attempt == MAX_RETRIES:
                logger.error(
                    "Ollama call failed (attempt %d/%d, non-retryable or max retries): %s",
                    attempt, MAX_RETRIES, exc,
                )
                raise

            wait = RETRY_BACKOFF_BASE * (2 ** (attempt - 1))
            logger.warning(
                "⚠️  Ollama call failed (attempt %d/%d): %s — retrying in %ds …",
                attempt, MAX_RETRIES, exc, wait,
            )
            time.sleep(wait)

    # Should never reach here, but just in case
    raise last_exc  # type: ignore[misc]


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

    Includes the same retry logic as ``call_ollama()``.

    Returns:
        Parsed JSON (dict or list).
    """
    logger.debug("Calling Ollama (JSON mode) model=%s", model)
    raw = call_ollama(
        prompt,
        model=model,
        temperature=temperature,
        json_mode=True,
    )
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        logger.warning("Ollama JSON decode failed, returning raw text in wrapper")
        return {"raw": raw}
