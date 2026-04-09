"""
BugRewind LangGraph Workflow.

Defines the complete multi-agent workflow as a compiled LangGraph StateGraph:

    START → orchestrator → critic → coder → critic (loop) →
    docker_gen → validation → [pass?] → solomon → summary → END
                                ↘ [fail?] → critic (re-analyse)

The Critic ↔ Coder loop runs until either:
  • No issues remain, OR
  • ``max_iterations`` is reached.

After the loop, Docker configs are generated, the image is built (validation),
and if successful Solomon deploys the container.  If the build fails, the
error logs are fed back to the Critic for one more analysis pass.
"""

from __future__ import annotations

import logging

from langgraph.graph import StateGraph, START, END

from bugrewind.graph.state import BugRewindState
from bugrewind.agents.orchestrator import orchestrator_node
from bugrewind.agents.critic import critic_node
from bugrewind.agents.coder import coder_node, docker_gen_node
from bugrewind.agents.solomon import validation_node, solomon_node, summary_node

logger = logging.getLogger(__name__)


# ── Routing functions ──────────────────────────────────────────────────────


def should_continue_fixing(state: BugRewindState) -> str:
    """Decide whether to loop back to the Critic or move on to Docker gen.

    Returns:
        ``"critic"``     – if there are still issues AND we haven't hit the
                           iteration cap.
        ``"docker_gen"`` – otherwise.
    """
    iteration = state.get("iteration", 0)
    max_iter = state.get("max_iterations", 3)
    issues = state.get("issues", [])

    if iteration >= max_iter:
        logger.info("🔁 Max iterations (%d) reached → moving to Docker gen.", max_iter)
        return "docker_gen"

    if not issues:
        logger.info("🔁 No issues remaining → moving to Docker gen.")
        return "docker_gen"

    logger.info("🔁 Issues remain (iter %d/%d) → looping back to Critic.",
                iteration, max_iter)
    return "critic"


def should_deploy_or_retry(state: BugRewindState) -> str:
    """After validation (docker build), decide next step.

    Returns:
        ``"solomon"`` – build succeeded, proceed to deployment.
        ``"critic"``  – build failed, retry analysis with error logs.
    """
    status = state.get("docker_status", "")

    if status == "build_success":
        logger.info("✅ Build succeeded → deploying with Solomon.")
        return "solomon"
    else:
        logger.warning("❌ Build failed → sending logs back to Critic.")
        return "critic"


# ── Graph construction ─────────────────────────────────────────────────────


def build_workflow() -> StateGraph:
    """Construct and compile the BugRewind LangGraph workflow.

    Returns:
        A compiled ``StateGraph`` ready to be invoked with an initial state dict.
    """
    builder = StateGraph(BugRewindState)

    # Register all nodes
    builder.add_node("orchestrator", orchestrator_node)
    builder.add_node("critic", critic_node)
    builder.add_node("coder", coder_node)
    builder.add_node("docker_gen", docker_gen_node)
    builder.add_node("validation", validation_node)
    builder.add_node("solomon", solomon_node)
    builder.add_node("summary", summary_node)

    # ── Edges ──────────────────────────────────────────────────────────
    # START → Orchestrator
    builder.add_edge(START, "orchestrator")

    # Orchestrator → Critic (first analysis pass)
    builder.add_edge("orchestrator", "critic")

    # Critic → Coder (always – the coder decides whether to patch or skip)
    builder.add_edge("critic", "coder")

    # Coder → conditional: loop back to Critic OR proceed to Docker gen
    builder.add_conditional_edges(
        "coder",
        should_continue_fixing,
        {
            "critic": "critic",
            "docker_gen": "docker_gen",
        },
    )

    # Docker gen → Validation (build the image)
    builder.add_edge("docker_gen", "validation")

    # Validation → conditional: deploy OR retry
    builder.add_conditional_edges(
        "validation",
        should_deploy_or_retry,
        {
            "solomon": "solomon",
            "critic": "critic",
        },
    )

    # Solomon → Summary
    builder.add_edge("solomon", "summary")

    # Summary → END
    builder.add_edge("summary", END)

    # Compile
    workflow = builder.compile()
    logger.info("LangGraph workflow compiled successfully.")
    return workflow


def run_workflow(
    repo_path: str,
    deploy_prompt: str = "Deploy this project securely via Docker.",
    max_iterations: int = 3,
) -> BugRewindState:
    """Build and invoke the workflow end-to-end.

    Args:
        repo_path:      Absolute path to the target repository.
        deploy_prompt:  User intent / deployment instructions.
        max_iterations: Max Critic↔Coder loop iterations.

    Returns:
        The final state dict after the workflow completes.
    """
    workflow = build_workflow()

    initial_state: BugRewindState = {
        "repo_path": repo_path,
        "deploy_prompt": deploy_prompt,
        "codebase": "",
        "file_manifest": {},
        "plan": "",
        "issues": [],
        "patches": [],
        "iteration": 0,
        "max_iterations": max_iterations,
        "dockerfile": "",
        "dockerignore": "",
        "docker_build_log": "",
        "docker_run_log": "",
        "docker_status": "",
        "logs": "[BugRewind] Workflow started.",
        "summary": "",
    }

    logger.info("🚀 Starting BugRewind workflow for %s", repo_path)
    final_state = workflow.invoke(initial_state)
    logger.info("🏁 Workflow complete. Docker status: %s",
                final_state.get("docker_status", "unknown"))

    return final_state
