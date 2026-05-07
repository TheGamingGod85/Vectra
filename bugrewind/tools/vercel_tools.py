"""
Vectra Vercel Tools.

Provides helpers for deploying FastAPI applications to Vercel via the
Vercel CLI (``vercel``).  Mirrors the ``docker_tools`` pattern — each
function shells out to the CLI and returns ``(success, log)``.

Vercel deploys Python/FastAPI apps as *Serverless Functions* using the
``@vercel/python`` builder.  The helpers here handle:

- Scaffolding the required ``vercel.json`` configuration
- Generating a ``requirements.txt`` from the project's dependencies
- Linking/creating a Vercel project
- Deploying (preview and production)
- Inspecting deployment status and fetching logs
"""

from __future__ import annotations

import json
import logging
import os
import subprocess
from pathlib import Path

logger = logging.getLogger(__name__)

VERCEL_TIMEOUT = 180  # seconds


# ── Configuration Scaffolding ──────────────────────────────────────────


def vercel_generate_config(
    project_path: str,
    entry_point: str = "api/main.py",
    app_variable: str = "app",
) -> tuple[bool, str]:
    """Generate a ``vercel.json`` for deploying a FastAPI app.

    Creates the standard Vercel configuration that routes all traffic
    to a single Python serverless function.  Also ensures the entry-point
    directory (``api/``) exists.

    Args:
        project_path:  Absolute path to the project root.
        entry_point:   Relative path to the FastAPI module
                       (default ``api/main.py``).
        app_variable:  Name of the FastAPI instance in the entry module.

    Returns:
        ``(success: bool, log: str)``
    """
    try:
        root = Path(project_path)
        entry_dir = root / Path(entry_point).parent
        entry_dir.mkdir(parents=True, exist_ok=True)

        config = {
            "version": 2,
            "builds": [
                {
                    "src": entry_point,
                    "use": "@vercel/python",
                }
            ],
            "routes": [
                {
                    "src": "/(.*)",
                    "dest": entry_point,
                }
            ],
        }

        config_path = root / "vercel.json"
        config_path.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")

        logger.info("Generated vercel.json at %s", config_path)
        return True, f"vercel.json written to {config_path}"

    except Exception as exc:
        msg = f"Failed to generate vercel.json: {exc}"
        logger.error(msg)
        return False, msg


def vercel_generate_requirements(
    project_path: str,
    extra_deps: list[str] | None = None,
) -> tuple[bool, str]:
    """Generate a ``requirements.txt`` suitable for Vercel's Python builder.

    Includes ``fastapi`` and ``uvicorn`` by default, plus any extras.

    Args:
        project_path:  Absolute path to the project root.
        extra_deps:    Additional pip packages to include.

    Returns:
        ``(success: bool, log: str)``
    """
    try:
        deps = ["fastapi", "uvicorn"]
        if extra_deps:
            deps.extend(extra_deps)

        # De-duplicate while preserving order
        seen: set[str] = set()
        unique: list[str] = []
        for d in deps:
            key = d.lower().split("==")[0].split(">=")[0].split("<=")[0]
            if key not in seen:
                seen.add(key)
                unique.append(d)

        req_path = Path(project_path) / "requirements.txt"
        req_path.write_text("\n".join(unique) + "\n", encoding="utf-8")

        logger.info("Generated requirements.txt with %d packages", len(unique))
        return True, f"requirements.txt written ({', '.join(unique)})"

    except Exception as exc:
        msg = f"Failed to generate requirements.txt: {exc}"
        logger.error(msg)
        return False, msg


# ── CLI Wrappers ───────────────────────────────────────────────────────


def _run_vercel(
    args: list[str],
    cwd: str,
    token: str | None = None,
    timeout: int = VERCEL_TIMEOUT,
) -> tuple[bool, str]:
    """Internal helper that invokes the Vercel CLI.

    Automatically appends ``--yes`` to suppress interactive prompts and
    ``--token`` when provided (or reads ``VERCEL_TOKEN`` from the env).

    Args:
        args:    Sub-command + flags (e.g. ``["deploy", "--prod"]``).
        cwd:     Working directory for the CLI.
        token:   Vercel auth token.  Falls back to ``$VERCEL_TOKEN``.
        timeout: Max seconds to wait.

    Returns:
        ``(success: bool, log: str)``
    """
    resolved_token = token or os.environ.get("VERCEL_TOKEN")

    cmd = ["vercel", *args, "--yes"]
    if resolved_token:
        cmd.extend(["--token", resolved_token])

    logger.info("Running: %s in %s", " ".join(cmd), cwd)

    try:
        result = subprocess.run(
            cmd,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        log = result.stdout + "\n" + result.stderr
        success = result.returncode == 0

        if success:
            logger.info("Vercel command succeeded: %s", " ".join(args))
        else:
            logger.error(
                "Vercel command FAILED (rc=%d): %s", result.returncode, " ".join(args)
            )

        return success, log.strip()

    except subprocess.TimeoutExpired:
        msg = f"Vercel command timed out after {timeout}s"
        logger.error(msg)
        return False, msg
    except FileNotFoundError:
        msg = (
            "Vercel CLI not found.  Install it with: npm i -g vercel\n"
            "Then authenticate with: vercel login"
        )
        logger.error(msg)
        return False, msg


def vercel_link(
    project_path: str,
    token: str | None = None,
) -> tuple[bool, str]:
    """Link the local directory to a Vercel project.

    Creates the ``.vercel/`` directory which binds the folder to a
    remote Vercel project.

    Args:
        project_path:  Absolute path to the project root.
        token:         Optional Vercel auth token.

    Returns:
        ``(success: bool, log: str)``
    """
    logger.info("🔗 Linking Vercel project in %s", project_path)
    return _run_vercel(["link"], cwd=project_path, token=token)


def vercel_deploy(
    project_path: str,
    prod: bool = False,
    token: str | None = None,
) -> tuple[bool, str]:
    """Deploy the project to Vercel.

    Args:
        project_path:  Absolute path to the project root.
        prod:          If True, deploys to production.
        token:         Optional Vercel auth token.

    Returns:
        ``(success: bool, log: str)`` – on success, the log contains the
        deployment URL printed by the CLI.
    """
    args = ["deploy"]
    if prod:
        args.append("--prod")

    env_label = "production" if prod else "preview"
    logger.info("🚀 Deploying to Vercel (%s) from %s", env_label, project_path)

    success, log = _run_vercel(args, cwd=project_path, token=token)

    if success:
        # Extract the deployment URL (last non-empty line from stdout is the URL)
        lines = [ln.strip() for ln in log.splitlines() if ln.strip()]
        url = lines[0] if lines else "unknown"
        logger.info("✅ Vercel deployment URL: %s", url)

    return success, log


def vercel_inspect(
    deployment_url: str,
    project_path: str,
    token: str | None = None,
) -> tuple[bool, str]:
    """Inspect a Vercel deployment to get its status and metadata.

    Args:
        deployment_url:  The deployment URL returned by ``vercel deploy``.
        project_path:    Absolute path to the project root (for CLI context).
        token:           Optional Vercel auth token.

    Returns:
        ``(success: bool, log: str)``
    """
    logger.info("🔍 Inspecting deployment: %s", deployment_url)
    return _run_vercel(["inspect", deployment_url], cwd=project_path, token=token)


def vercel_logs(
    deployment_url: str,
    project_path: str,
    token: str | None = None,
) -> tuple[bool, str]:
    """Fetch runtime logs for a Vercel deployment.

    Args:
        deployment_url:  The deployment URL.
        project_path:    Absolute path to the project root.
        token:           Optional Vercel auth token.

    Returns:
        ``(success: bool, log: str)``
    """
    logger.info("📜 Fetching logs for: %s", deployment_url)
    return _run_vercel(["logs", deployment_url], cwd=project_path, token=token)


def vercel_env_add(
    project_path: str,
    key: str,
    value: str,
    environment: str = "production",
    token: str | None = None,
) -> tuple[bool, str]:
    """Add an environment variable to the Vercel project.

    Args:
        project_path:  Absolute path to the project root.
        key:           Variable name.
        value:         Variable value.
        environment:   Target environment (``production``, ``preview``, ``development``).
        token:         Optional Vercel auth token.

    Returns:
        ``(success: bool, log: str)``
    """
    logger.info("🔑 Setting env var %s for %s", key, environment)

    resolved_token = token or os.environ.get("VERCEL_TOKEN")
    cmd = ["vercel", "env", "add", key, environment, "--yes"]
    if resolved_token:
        cmd.extend(["--token", resolved_token])

    try:
        result = subprocess.run(
            cmd,
            cwd=project_path,
            input=value,
            capture_output=True,
            text=True,
            timeout=VERCEL_TIMEOUT,
        )
        log = result.stdout + "\n" + result.stderr
        success = result.returncode == 0

        if success:
            logger.info("Env var %s set for %s", key, environment)
        else:
            logger.error("Failed to set env var %s (rc=%d)", key, result.returncode)

        return success, log.strip()

    except subprocess.TimeoutExpired:
        msg = f"Vercel env command timed out after {VERCEL_TIMEOUT}s"
        logger.error(msg)
        return False, msg
    except FileNotFoundError:
        msg = "Vercel CLI not found.  Install it with: npm i -g vercel"
        logger.error(msg)
        return False, msg


def vercel_remove(
    deployment_url: str,
    project_path: str,
    token: str | None = None,
) -> tuple[bool, str]:
    """Remove / tear down a Vercel deployment.

    Args:
        deployment_url:  The deployment URL to remove.
        project_path:    Absolute path to the project root.
        token:           Optional Vercel auth token.

    Returns:
        ``(success: bool, log: str)``
    """
    logger.info("🗑️ Removing deployment: %s", deployment_url)
    return _run_vercel(
        ["remove", deployment_url, "--safe"],
        cwd=project_path,
        token=token,
    )
