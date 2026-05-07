"""
Sentinel State Definition.

Defines the ``WatcherState`` TypedDict that flows through the
post-mortem LangGraph workflow.  Each field captures a facet of
the forensic analysis — from raw container data to the final
fix recommendation dispatched via email.
"""

from __future__ import annotations

from typing import TypedDict


class WatcherState(TypedDict):
    """Shared state for the Sentinel post-mortem workflow.

    Attributes:
        container_id:         Docker container ID or name.
        repo_path:            Absolute path to the repository that produced the image.
        exit_code:            The exit code reported by the crashed container.
        is_oom_killed:        Whether the container was terminated due to OOM.
        container_logs:       Last 100 lines of container stdout/stderr.
        source_code_context:  Manifest or snippet of the codebase read from ``repo_path``.
        root_cause_category:  Classification — ``'infrastructure'``, ``'source_code'``,
                              or ``'unknown'``.
        diagnostic_report:    Detailed report produced by the PM Critic node.
        fix_recommendation:   Actionable fix produced by the PM Coder node.
        target_email:         E-mail address to receive the notification.
    """

    container_id: str
    repo_path: str
    exit_code: int
    is_oom_killed: bool
    container_logs: str
    source_code_context: str
    root_cause_category: str
    diagnostic_report: str
    fix_recommendation: str
    target_email: str
