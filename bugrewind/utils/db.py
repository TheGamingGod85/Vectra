"""
Vectra Database Utility.

Initialises and provides access to the SQLite database
``monitored_containers.sqlite`` stored in the project root.
The database tracks containers deployed by Vectra so that
Sentinel can monitor them independently.
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
    deployed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    diagnostic_report TEXT,
    fix_recommendation TEXT,
    container_logs TEXT,
    root_cause_category TEXT
);
"""


def _get_connection() -> sqlite3.Connection:
    """Return a connection to the monitored-containers database.

    Creates the database file and schema if they don't already exist.
    """
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute(_CREATE_TABLE_SQL)
    
    # Simple migration: attempt to add new columns if missing (ignores error if they exist)
    for col in ["diagnostic_report", "fix_recommendation", "container_logs", "root_cause_category"]:
        try:
            conn.execute(f"ALTER TABLE containers ADD COLUMN {col} TEXT")
        except sqlite3.OperationalError:
            pass
            
    conn.commit()
    return conn

def save_container_diagnostics(record_id: str, result: dict) -> None:
    """Save post-mortem AI diagnostics to the database.
    
    Args:
        record_id: UUID for the database row.
        result: The WatcherState result containing diagnostic fields.
    """
    conn = _get_connection()
    try:
        cursor = conn.execute("SELECT repository_path FROM containers WHERE id = ?", (record_id,))
        row = cursor.fetchone()
        repo_path = row["repository_path"] if row else None

        conn.execute(
            """UPDATE containers 
               SET diagnostic_report = ?, 
                   fix_recommendation = ?, 
                   container_logs = ?, 
                   root_cause_category = ? 
               WHERE id = ?""",
            (
                result.get("diagnostic_report", ""),
                result.get("fix_recommendation", ""),
                result.get("container_logs", ""),
                result.get("root_cause_category", ""),
                record_id,
            ),
        )
        conn.commit()
        logger.info("Saved full diagnostic conversation for %s", record_id)

        if repo_path:
            import datetime
            deployments_dir = Path(repo_path) / ".deployments"
            deployments_dir.mkdir(parents=True, exist_ok=True)
            
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            report_file = deployments_dir / f"diagnostic_{record_id[:8]}_{timestamp}.md"
            
            content = f"# Diagnostic Report\n\n"
            content += f"**Root Cause**: {result.get('root_cause_category', 'Unknown')}\n\n"
            content += "## Analysis\n\n"
            content += f"{result.get('diagnostic_report', '')}\n\n"
            content += "## Fix Recommendation\n\n"
            content += f"{result.get('fix_recommendation', '')}\n\n"
            content += "## Logs\n\n```text\n"
            content += f"{result.get('container_logs', '')}\n```\n"

            report_file.write_text(content, encoding="utf-8")
            logger.info("Saved diagnostic markdown file to %s", report_file)
    finally:
        conn.close()


def insert_container(
    record_id: str,
    container_id: str,
    repository_path: str,
    target_email: str = "marcus32holloway@gmail.com",
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

def get_all_containers() -> list[dict]:
    """Return all container records.

    Returns:
        A list of dicts with keys matching the table columns.
    """
    conn = _get_connection()
    try:
        cursor = conn.execute(
            "SELECT * "
            "FROM containers ORDER BY deployed_at DESC"
        )
        return [dict(row) for row in cursor.fetchall()]
    finally:
        conn.close()

def delete_container(record_id: str) -> None:
    """Delete a container record from the monitoring database.

    Args:
        record_id: The UUID primary key.
    """
    conn = _get_connection()
    try:
        conn.execute(
            "DELETE FROM containers WHERE id = ?",
            (record_id,),
        )
        conn.commit()
        logger.info("Deleted container %s", record_id)
    finally:
        conn.close()
