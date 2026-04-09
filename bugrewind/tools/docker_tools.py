"""
BugRewind Docker Tools.

Provides ``docker_build`` and ``docker_run`` helpers that shell out to the
Docker CLI via ``subprocess``.  Only the Solomon agent should invoke these.
"""

from __future__ import annotations

import logging
import subprocess
from pathlib import Path

logger = logging.getLogger(__name__)

DOCKER_TIMEOUT = 300  # seconds


def docker_build(
    context_path: str,
    tag: str = "bugrewind-app:latest",
) -> tuple[bool, str]:
    """Run ``docker build`` on the given context directory.

    Args:
        context_path: Absolute path to the directory containing the Dockerfile.
        tag:          Image tag to apply.

    Returns:
        ``(success: bool, log: str)`` – success is True when the build exits 0.
    """
    cmd = ["docker", "build", "-t", tag, "."]
    logger.info("Running: %s in %s", " ".join(cmd), context_path)

    try:
        result = subprocess.run(
            cmd,
            cwd=context_path,
            capture_output=True,
            text=True,
            timeout=DOCKER_TIMEOUT,
        )
        log = result.stdout + "\n" + result.stderr
        success = result.returncode == 0

        if success:
            logger.info("Docker build succeeded for tag=%s", tag)
        else:
            logger.error("Docker build FAILED (rc=%d)", result.returncode)

        return success, log.strip()

    except subprocess.TimeoutExpired:
        msg = f"Docker build timed out after {DOCKER_TIMEOUT}s"
        logger.error(msg)
        return False, msg
    except FileNotFoundError:
        msg = "Docker CLI not found. Is Docker installed and in PATH?"
        logger.error(msg)
        return False, msg


def docker_run(
    tag: str = "bugrewind-app:latest",
    container_name: str = "bugrewind-container",
    ports: str | None = None,
    detach: bool = True,
    health_check_seconds: int = 5,
) -> tuple[bool, str]:
    """Run a container from the given image tag.

    If ``detach`` is True the container is started in the background and we
    briefly wait to confirm it hasn't immediately crashed.

    Args:
        tag:                   Image to run.
        container_name:        Name for the container (auto-removed first).
        ports:                 Optional port mapping, e.g. ``"8000:8000"``.
        detach:                Run in detached mode.
        health_check_seconds:  Seconds to wait before checking container status.

    Returns:
        ``(success: bool, log: str)``
    """
    # Remove any existing container with the same name
    subprocess.run(
        ["docker", "rm", "-f", container_name],
        capture_output=True,
        text=True,
    )

    cmd = ["docker", "run", "--name", container_name]
    if detach:
        cmd.append("-d")
    if ports:
        cmd.extend(["-p", ports])
    cmd.append(tag)

    logger.info("Running: %s", " ".join(cmd))

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=DOCKER_TIMEOUT,
        )
        log = result.stdout + "\n" + result.stderr

        if result.returncode != 0:
            logger.error("Docker run FAILED (rc=%d)", result.returncode)
            return False, log.strip()

        if detach:
            # Wait briefly, then inspect container state
            import time
            time.sleep(health_check_seconds)

            inspect = subprocess.run(
                ["docker", "inspect", "-f", "{{.State.Running}}", container_name],
                capture_output=True,
                text=True,
            )
            is_running = inspect.stdout.strip().lower() == "true"

            if is_running:
                logger.info("Container %s is running", container_name)
                return True, f"Container {container_name} started successfully.\n{log.strip()}"
            else:
                # Grab logs from the crashed container
                logs_result = subprocess.run(
                    ["docker", "logs", container_name],
                    capture_output=True,
                    text=True,
                )
                crash_log = logs_result.stdout + "\n" + logs_result.stderr
                logger.error("Container exited immediately")
                return False, f"Container exited immediately.\n{crash_log.strip()}"

        return True, log.strip()

    except subprocess.TimeoutExpired:
        msg = f"Docker run timed out after {DOCKER_TIMEOUT}s"
        logger.error(msg)
        return False, msg
    except FileNotFoundError:
        msg = "Docker CLI not found. Is Docker installed and in PATH?"
        logger.error(msg)
        return False, msg


def docker_stop(container_name: str = "bugrewind-container") -> tuple[bool, str]:
    """Stop and remove a running container.

    Returns:
        ``(success: bool, log: str)``
    """
    try:
        result = subprocess.run(
            ["docker", "rm", "-f", container_name],
            capture_output=True,
            text=True,
            timeout=30,
        )
        return result.returncode == 0, (result.stdout + result.stderr).strip()
    except Exception as exc:
        return False, str(exc)
