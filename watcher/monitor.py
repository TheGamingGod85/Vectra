"""
RewindWatcher Monitoring Daemon.

Standalone foreground-blocking process that polls Docker for crashed
containers every 10 minutes and triggers the post-mortem AI workflow.

Usage::

    python watcher/monitor.py

The daemon:
1. Reads the ``monitored_containers.sqlite`` database for containers
   with ``status = 'monitoring'``.
2. Uses the Docker Python SDK to check each container's health.
3. If a container has ``exited``, extracts forensic data (exit code,
   OOM status, last 100 log lines).
4. Triggers the LangGraph post-mortem workflow.
5. Updates the database status to ``'notified'`` upon completion.

Graceful failure: if the LLM is down or times out, the error is logged
but the watcher loop continues — the container will be retried on the
next polling cycle.
"""

from __future__ import annotations

import asyncio
import logging
import sys
import signal
from pathlib import Path

# Ensure the project root is on sys.path so both bugrewind and watcher
# packages can be imported regardless of the working directory.
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

import docker
from docker.errors import NotFound as DockerNotFound, APIError as DockerAPIError

from bugrewind.utils.db import (
    get_monitoring_containers,
    update_container_status,
    save_container_diagnostics,
)
from watcher.graph import run_watcher_workflow

# ── Logging setup ──────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(name)-28s  %(levelname)-7s  %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("rewindwatcher")

# ── Configuration ──────────────────────────────────────────────────────────
POLL_INTERVAL_SECONDS = 10 * 60  # 10 minutes


def _extract_forensics(client: docker.DockerClient, container_id: str) -> dict | None:
    """Collect forensic data from an exited Docker container.

    Args:
        client:       Docker SDK client instance.
        container_id: The container ID or name.

    Returns:
        A dict with ``exit_code``, ``is_oom_killed``, and ``container_logs``,
        or ``None`` if the container cannot be found.
    """
    try:
        container = client.containers.get(container_id)
    except DockerNotFound:
        logger.warning("Container %s not found in Docker — skipping.", container_id)
        return None
    except DockerAPIError as exc:
        logger.error("Docker API error for %s: %s", container_id, exc)
        return None

    state = container.attrs.get("State", {})
    exit_code = state.get("ExitCode", -1)
    is_oom_killed = state.get("OOMKilled", False)

    try:
        raw_logs = container.logs(tail=100, timestamps=False)
        if isinstance(raw_logs, bytes):
            container_logs = raw_logs.decode("utf-8", errors="replace")
        else:
            container_logs = str(raw_logs)
    except Exception as exc:
        logger.warning("Could not fetch logs for %s: %s", container_id, exc)
        container_logs = f"(unable to retrieve logs: {exc})"

    return {
        "exit_code": exit_code,
        "is_oom_killed": is_oom_killed,
        "container_logs": container_logs,
    }


def _check_container_health(
    client: docker.DockerClient,
    container_id: str,
) -> str | None:
    """Return the Docker status of a container, or ``None`` if not found.

    Common statuses: ``'running'``, ``'exited'``, ``'paused'``, ``'restarting'``.
    """
    try:
        container = client.containers.get(container_id)
        return container.status
    except DockerNotFound:
        logger.warning("Container %s no longer exists.", container_id)
        return None
    except DockerAPIError as exc:
        logger.error("Docker API error checking %s: %s", container_id, exc)
        return None


def poll_once(client: docker.DockerClient) -> int:
    """Run a single polling cycle.

    Queries the database for all containers with ``status = 'monitoring'``,
    checks their Docker health, and triggers post-mortem analysis for any
    that have exited.

    Returns:
        The number of containers that were analysed in this cycle.
    """
    containers = get_monitoring_containers()
    if not containers:
        logger.debug("No containers to monitor.")
        return 0

    logger.info("🔎 Checking %d monitored container(s) …", len(containers))
    analysed = 0

    for record in containers:
        record_id = record["id"]
        container_id = record["container_id"]
        repo_path = record["repository_path"]
        target_email = record["target_email"]

        docker_status = _check_container_health(client, container_id)

        if docker_status is None:
            # Container no longer exists — mark as lost
            update_container_status(record_id, "lost")
            continue

        if docker_status == "running":
            logger.debug("Container %s is healthy (running).", container_id)
            continue

        if docker_status != "exited":
            logger.info(
                "Container %s has status '%s' — not acting yet.",
                container_id, docker_status,
            )
            continue

        # ── Container has exited — begin forensics ───────────────────────
        logger.info(
            "💀 Container %s has EXITED — starting post-mortem analysis …",
            container_id,
        )
        update_container_status(record_id, "analyzing")

        forensics = _extract_forensics(client, container_id)
        if forensics is None:
            update_container_status(record_id, "forensics_failed")
            continue

        try:
            result = run_watcher_workflow(
                container_id=container_id,
                repo_path=repo_path,
                exit_code=forensics["exit_code"],
                is_oom_killed=forensics["is_oom_killed"],
                container_logs=forensics["container_logs"],
                target_email=target_email,
            )
            save_container_diagnostics(record_id, result)
            update_container_status(record_id, "notified")
            analysed += 1
        except Exception as exc:
            logger.error(
                "⚠️  Post-mortem workflow failed for %s: %s — "
                "will retry on next cycle.",
                container_id, exc,
            )
            # Revert to monitoring so it gets picked up next cycle
            update_container_status(record_id, "monitoring")

    return analysed


async def _run_loop() -> None:
    """Async polling loop that runs indefinitely.

    Polls every ``POLL_INTERVAL_SECONDS`` (default 10 minutes).
    Graceful failure: any LLM or Docker error is logged but does NOT
    crash the loop.
    """
    logger.info("=" * 60)
    logger.info("  RewindWatcher Monitoring Daemon Started")
    logger.info("  Polling interval: %d seconds (%d minutes)",
                POLL_INTERVAL_SECONDS, POLL_INTERVAL_SECONDS // 60)
    logger.info("=" * 60)

    try:
        client = docker.from_env()
        client.ping()
        logger.info("✅ Docker daemon connection verified.")
    except Exception as exc:
        logger.error(
            "❌ Cannot connect to Docker daemon: %s\n"
            "   Make sure Docker Desktop is running.",
            exc,
        )
        return

    while True:
        try:
            poll_once(client)
        except Exception as exc:
            logger.error(
                "⚠️  Unhandled error during poll cycle: %s — continuing …",
                exc,
            )

        logger.info(
            "💤 Next poll in %d minutes. Press Ctrl+C to stop.",
            POLL_INTERVAL_SECONDS // 60,
        )
        await asyncio.sleep(POLL_INTERVAL_SECONDS)


def main() -> None:
    """Entry point for ``python watcher/monitor.py``."""
    loop = asyncio.new_event_loop()

    # Handle Ctrl+C gracefully
    def _signal_handler(sig, frame):
        logger.info("\n🛑 Shutting down RewindWatcher …")
        loop.stop()
        sys.exit(0)

    signal.signal(signal.SIGINT, _signal_handler)

    try:
        loop.run_until_complete(_run_loop())
    except KeyboardInterrupt:
        logger.info("\n🛑 Shutting down RewindWatcher …")
    finally:
        loop.close()


if __name__ == "__main__":
    main()
