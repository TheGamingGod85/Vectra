"""
Vectra Central Configuration.

Every tunable that was previously hardcoded across the codebase lives here,
read once from environment variables with sensible defaults.  Import the
module-level constants directly::

    from vectra.config import OLLAMA_URL, DEFAULT_MODEL

Environment variables:

    VECTRA_OLLAMA_URL             Ollama generate endpoint
                                  (default: http://localhost:11434/api/generate)
    VECTRA_OLLAMA_MODEL           Model tag (default: minimax-m3:cloud)
    VECTRA_LLM_TIMEOUT            LLM request timeout in seconds (default: 500)

    VECTRA_TARGET_EMAIL           Recipient for Sentinel crash alerts.
                                  Empty (default) → alerts are logged to the
                                  console instead of emailed.
    VECTRA_SMTP_HOST              SMTP server (default: smtp.gmail.com)
    VECTRA_SMTP_PORT              SMTP port (default: 587)
    SMTP_USER                     SMTP login / sender address
    SMTP_APP_PASSWORD             SMTP app password

    VECTRA_DOCKER_TIMEOUT         docker build/run timeout in seconds (default: 600)
    VECTRA_POLL_INTERVAL_SECONDS  Sentinel polling interval (default: 600)

    VECTRA_AUTO_INSTALL_DEPS      "1" (default) → auto-install packages that
                                  LLM patches introduce.  "0" → only update
                                  dependency files, never run installers.
    VECTRA_VERCEL_PROD            "0" (default) → Vercel deploys go to a
                                  preview URL.  "1" → deploy to production.
"""

from __future__ import annotations

import os


def _env_bool(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in ("1", "true", "yes", "on")


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


# ── LLM ─────────────────────────────────────────────────────────────────────
OLLAMA_URL: str = os.environ.get(
    "VECTRA_OLLAMA_URL", "http://localhost:11434/api/generate"
)
DEFAULT_MODEL: str = os.environ.get("VECTRA_OLLAMA_MODEL", "minimax-m3:cloud")
LLM_TIMEOUT: float = float(_env_int("VECTRA_LLM_TIMEOUT", 500))

# ── Notifications ───────────────────────────────────────────────────────────
TARGET_EMAIL: str = os.environ.get("VECTRA_TARGET_EMAIL", "")
SMTP_HOST: str = os.environ.get("VECTRA_SMTP_HOST", "smtp.gmail.com")
SMTP_PORT: int = _env_int("VECTRA_SMTP_PORT", 587)
SMTP_USER: str = os.environ.get("SMTP_USER", "")
SMTP_APP_PASSWORD: str = os.environ.get("SMTP_APP_PASSWORD", "")

# ── Docker / deployment ─────────────────────────────────────────────────────
DOCKER_TIMEOUT: int = _env_int("VECTRA_DOCKER_TIMEOUT", 600)
DEFAULT_APP_PORT: int = 8000

# ── Sentinel ────────────────────────────────────────────────────────────────
POLL_INTERVAL_SECONDS: int = _env_int("VECTRA_POLL_INTERVAL_SECONDS", 600)

# ── Behaviour flags ─────────────────────────────────────────────────────────
AUTO_INSTALL_DEPS: bool = _env_bool("VECTRA_AUTO_INSTALL_DEPS", True)
VERCEL_PROD: bool = _env_bool("VECTRA_VERCEL_PROD", False)
