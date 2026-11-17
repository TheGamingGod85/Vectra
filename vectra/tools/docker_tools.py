"""
Vectra Docker Tools.

Provides ``docker_build`` and ``docker_run`` helpers that shell out to the
Docker CLI via ``subprocess``.  Only the Solomon agent should invoke these.
"""

from __future__ import annotations

import logging
import re
import subprocess
import time
from pathlib import Path

from vectra.config import DOCKER_TIMEOUT, DEFAULT_APP_PORT

logger = logging.getLogger(__name__)


def detect_exposed_port(dockerfile_text: str) -> int | None:
    """Return the first port declared via ``EXPOSE`` in a Dockerfile.

    Returns ``None`` when no EXPOSE instruction is present (e.g. a CLI app).
    """
    for m in re.finditer(
        r"^\s*EXPOSE\s+(\d+)", dockerfile_text, re.IGNORECASE | re.MULTILINE
    ):
        return int(m.group(1))
    return None


def docker_build(
    context_path: str,
    tag: str = "vectra-app:latest",
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


def _http_probe(port: int, timeout_seconds: int = 15) -> tuple[bool, str]:
    """Try to reach ``http://localhost:<port>/`` until it responds or times out.

    Any HTTP status code counts as reachable — a 404 still proves the server
    is up and the port mapping works.
    """
    import httpx

    deadline = time.monotonic() + timeout_seconds
    last_error = ""
    while time.monotonic() < deadline:
        try:
            response = httpx.get(f"http://localhost:{port}/", timeout=3.0)
            return True, f"HTTP probe: got status {response.status_code} on port {port}"
        except Exception as exc:
            last_error = str(exc)
            time.sleep(1.0)
    return False, f"HTTP probe: no response on port {port} after {timeout_seconds}s ({last_error})"


def docker_run(
    tag: str = "vectra-app:latest",
    container_name: str = "vectra-container",
    ports: str | None = None,
    env_file: str | None = None,
    detach: bool = True,
    health_check_seconds: int = 5,
) -> tuple[bool, str, str]:
    """Run a container from the given image tag.

    If ``detach`` is True the container is started in the background and we
    briefly wait to confirm it hasn't immediately crashed.  When a port
    mapping is supplied, an HTTP probe against the host port is attempted
    and its outcome appended to the log (informational — a non-HTTP app
    won't fail deployment because of it).

    Args:
        tag:                   Image to run.
        container_name:        Name for the container (auto-removed first).
        ports:                 Optional port mapping, e.g. ``"8000:8000"``.
        env_file:              Optional path to an env file passed via
                               ``--env-file`` so extracted secrets reach the
                               container at runtime.
        detach:                Run in detached mode.
        health_check_seconds:  Seconds to wait before checking container status.

    Returns:
        ``(success: bool, log: str, container_id: str)`` – container_id is the
        full ID printed by ``docker run -d`` (empty string on failure).
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
    if env_file:
        cmd.extend(["--env-file", env_file])
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
            return False, log.strip(), ""

        # `docker run -d` prints the container ID on stdout
        container_id = result.stdout.strip().splitlines()[-1] if result.stdout.strip() else ""

        if detach:
            # Wait briefly, then inspect container state
            time.sleep(health_check_seconds)

            inspect = subprocess.run(
                ["docker", "inspect", "-f", "{{.State.Running}}", container_name],
                capture_output=True,
                text=True,
            )
            is_running = inspect.stdout.strip().lower() == "true"

            if not is_running:
                # Grab logs from the crashed container
                logs_result = subprocess.run(
                    ["docker", "logs", container_name],
                    capture_output=True,
                    text=True,
                )
                crash_log = logs_result.stdout + "\n" + logs_result.stderr
                logger.error("Container exited immediately")
                return False, f"Container exited immediately.\n{crash_log.strip()}", container_id

            probe_note = ""
            if ports:
                host_port = int(ports.split(":", 1)[0])
                probe_ok, probe_msg = _http_probe(host_port)
                probe_note = "\n" + probe_msg
                if probe_ok:
                    logger.info(probe_msg)
                else:
                    logger.warning("%s — container is running but may not serve HTTP.", probe_msg)

            logger.info("Container %s is running", container_name)
            return True, f"Container {container_name} started successfully.{probe_note}\n{log.strip()}", container_id

        return True, log.strip(), container_id

    except subprocess.TimeoutExpired:
        msg = f"Docker run timed out after {DOCKER_TIMEOUT}s"
        logger.error(msg)
        return False, msg, ""
    except FileNotFoundError:
        msg = "Docker CLI not found. Is Docker installed and in PATH?"
        logger.error(msg)
        return False, msg, ""


def docker_stop(container_name: str = "vectra-container") -> tuple[bool, str]:
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
