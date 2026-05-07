"""
Sentinel Post-Mortem LangGraph Workflow.

Defines a three-node workflow that operates entirely independently
of Vectra's main deployment graph:

    PM Critic → PM Coder → Dispatcher

The workflow takes a ``WatcherState`` populated with forensic data
from a crashed container and produces a diagnostic report, fix
recommendation, and dispatches an email notification.
"""

from __future__ import annotations

import logging

from langgraph.graph import StateGraph, END

from sentinel.state import WatcherState
from sentinel.agents import pm_critic_node, pm_coder_node
from sentinel.notifier import dispatcher_node

logger = logging.getLogger(__name__)


def build_sentinel_graph() -> StateGraph:
    """Build and compile the Sentinel post-mortem LangGraph workflow.

    Returns:
        A compiled ``StateGraph`` ready to be invoked with a ``WatcherState``.
    """
    graph = StateGraph(WatcherState)

    # ── Add nodes ──────────────────────────────────────────────────────────
    graph.add_node("pm_critic", pm_critic_node)
    graph.add_node("pm_coder", pm_coder_node)
    graph.add_node("dispatcher", dispatcher_node)

    # ── Define edges ───────────────────────────────────────────────────────
    graph.set_entry_point("pm_critic")
    graph.add_edge("pm_critic", "pm_coder")
    graph.add_edge("pm_coder", "dispatcher")
    graph.add_edge("dispatcher", END)

    logger.info("Sentinel graph compiled: pm_critic → pm_coder → dispatcher")
    return graph.compile()


def run_sentinel_workflow(
    container_id: str,
    repo_path: str,
    exit_code: int,
    is_oom_killed: bool,
    container_logs: str,
    target_email: str,
) -> dict:
    """Execute the full post-mortem workflow for a crashed container.

    Args:
        container_id:  Docker container ID / name.
        repo_path:     Absolute path to the source repository.
        exit_code:     Container exit code.
        is_oom_killed: Whether the container was OOM-killed.
        container_logs: Last 100 lines of container logs.
        target_email:  E-mail address for the notification.

    Returns:
        The final state dict after all nodes have run.
    """
    compiled_graph = build_sentinel_graph()

    initial_state: WatcherState = {
        "container_id": container_id,
        "repo_path": repo_path,
        "exit_code": exit_code,
        "is_oom_killed": is_oom_killed,
        "container_logs": container_logs,
        "source_code_context": "",
        "root_cause_category": "",
        "diagnostic_report": "",
        "fix_recommendation": "",
        "target_email": target_email,
    }

    logger.info(
        "▶️  Starting post-mortem workflow for container %s (exit_code=%d, oom=%s)",
        container_id, exit_code, is_oom_killed,
    )

    result = compiled_graph.invoke(initial_state)

    logger.info(
        "✅ Post-mortem workflow complete for %s — category: %s",
        container_id, result.get("root_cause_category", "unknown"),
    )

    return result
