"""
BugRewind Database Utility.

Initialises and provides access to the SQLite database
``monitored_containers.sqlite`` stored in the project root.
The database tracks containers deployed by BugRewind so that
RewindWatcher can monitor them independently.
"""

from __future__ import annotations

import logging
import sqlite3
from pathlib import Path

logger = logging.getLogger(__name__)

# ── Database location ──────────────────────────────────────────────────────
DB_PATH = Path(__file__).resolve().parents[2] / "monitored_containers.sqlite"

# ── Schema ─────────────────────────────────────────────────────────────────
_CREATE_TABLE_SQL = """\
CREATE TABLE IF NOT EXISTS containers (
    id TEXT PRIMARY KEY,
    container_id TEXT NOT NULL,
    repository_path TEXT NOT NULL,
    target_email TEXT NOT NULL,
    status TEXT DEFAULT 'monitoring',
    deployed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""


def _get_connection() -> sqlite3.Connection:
    """Return a connection to the monitored-containers database.

    Creates the database file and schema if they don't already exist.
    """
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute(_CREATE_TABLE_SQL)
    conn.commit()
    return conn


def insert_container(
    record_id: str,
    container_id: str,
    repository_path: str,
    target_email: str = "admin@local.dev",
) -> None:
    """Insert a newly deployed container into the monitoring database.

    Args:
        record_id:       UUID for the database row.
        container_id:    Docker container ID / name.
        repository_path: Absolute path to the source repository.
        target_email:    E-mail address for crash notifications.
    """
    conn = _get_connection()
    try:
        conn.execute(
            "INSERT INTO containers (id, container_id, repository_path, target_email) "
            "VALUES (?, ?, ?, ?)",
            (record_id, container_id, repository_path, target_email),
        )
        conn.commit()
        logger.info(
            "Registered container %s (repo=%s) for monitoring.",
            container_id, repository_path,
        )
    finally:
        conn.close()


def get_monitoring_containers() -> list[dict]:
    """Return all containers whose status is ``'monitoring'``.

    Returns:
        A list of dicts with keys matching the table columns.
    """
    conn = _get_connection()
    try:
        cursor = conn.execute(
            "SELECT id, container_id, repository_path, target_email, status, deployed_at "
            "FROM containers WHERE status = 'monitoring'"
        )
        return [dict(row) for row in cursor.fetchall()]
    finally:
        conn.close()


def update_container_status(record_id: str, new_status: str) -> None:
    """Update the status of a container record.

    Args:
        record_id:  The UUID primary key.
        new_status: New status string (e.g. ``'analyzing'``, ``'notified'``).
    """
    conn = _get_connection()
    try:
        conn.execute(
            "UPDATE containers SET status = ? WHERE id = ?",
            (new_status, record_id),
        )
        conn.commit()
        logger.info("Updated container %s → status=%s", record_id, new_status)
    finally:
        conn.close()
