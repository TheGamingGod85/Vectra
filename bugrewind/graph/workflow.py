"""
Vectra LangGraph Workflow.

Defines the complete multi-agent workflow as a compiled LangGraph StateGraph:

  Docker path (default):
    START → orchestrator → critic → coder → critic (loop) →
    docker_gen → validation → [pass?] → solomon → summary → END
                                ↘ [fail?] → critic (re-analyse, max 2 retries)

  Vercel path (when user mentions vercel/serverless/cloud):
    START → orchestrator → critic → coder → critic (loop) →
    vercel_setup → vercel_deploy → summary → END

The Critic ↔ Coder loop runs until either:
  • No issues remain, OR
  • ``max_iterations`` is reached, OR
  • The coder is stuck (applied 0 patches with issues remaining).

After the loop, the ``deploy_target`` field (``"docker"`` or ``"vercel"``)
determines which deployment pipeline is used.
"""

from __future__ import annotations

import logging

from langgraph.graph import StateGraph, START, END

from vectra.graph.state import VectraState
from vectra.agents.orchestrator import orchestrator_node
from vectra.agents.critic import critic_node
from vectra.agents.coder import coder_node, docker_gen_node
from vectra.agents.solomon import (
    validation_node,
    solomon_node,
    vercel_setup_node,
    vercel_deploy_node,
    summary_node,
)

logger = logging.getLogger(__name__)

MAX_BUILD_RETRIES = 2  # max times to retry build-fail → critic → coder loop


# ── Routing functions ──────────────────────────────────────────────────────


def should_continue_fixing(state: VectraState) -> str:
    """Decide whether to loop back to the Critic or move on to deployment.

    Returns:
        ``"critic"``       – if there are still un-fixed issues AND the coder
                             actually made progress AND we haven't hit the
                             iteration cap.
        ``"deploy_route"`` – otherwise (proceed to deployment routing).
    """
    iteration = state.get("iteration", 0)
    max_iter = state.get("max_iterations", 3)
    current_issues = state.get("current_issues", [])
    last_patch_count = state.get("last_patch_count", 0)

    if iteration >= max_iter:
        logger.info("🔁 Max iterations (%d) reached → moving to deployment.", max_iter)
        return "deploy_route"

    if not current_issues:
        logger.info("🔁 No issues remaining → moving to deployment.")
        return "deploy_route"

    # If the coder failed to apply ANY patches but issues remain, we're stuck.
    # Don't loop back — it'll just find the same issues again.
    if last_patch_count == 0 and iteration > 0:
        logger.warning(
            "🔁 Coder applied 0 patches with %d issues remaining — "
            "stuck loop detected, moving to deployment.",
            len(current_issues),
        )
        return "deploy_route"

    logger.info("🔁 Issues remain (iter %d/%d) → looping back to Critic.",
                iteration, max_iter)
    return "critic"


def should_deploy_docker_or_vercel(state: VectraState) -> str:
    """Choose between Docker and Vercel deployment pipelines.

    Inspects ``state["deploy_target"]`` (set by ``run_workflow`` based on
    the user's prompt) to decide the deployment path.

    Returns:
        ``"docker_gen"``    – traditional Docker build + container deployment.
        ``"vercel_setup"``  – Vercel Serverless Function deployment.
    """
    target = state.get("deploy_target", "docker")

    if target == "vercel":
        logger.info("🌐 Deploy target is Vercel → routing to vercel_setup.")
        return "vercel_setup"

    logger.info("🐳 Deploy target is Docker → routing to docker_gen.")
    return "docker_gen"


def should_deploy_or_retry(state: VectraState) -> str:
    """After validation (docker build), decide next step.

    Returns:
        ``"solomon"`` – build succeeded, proceed to deployment.
        ``"critic"``  – build failed AND we haven't exceeded build retries.
        ``"solomon"`` – build failed BUT we've exhausted retries → deploy anyway
                        (solomon will handle the failed status gracefully).
    """
    status = state.get("docker_status", "")
    build_attempts = state.get("build_attempts", 1)

    if status == "build_success":
        logger.info("✅ Build succeeded → deploying with Solomon.")
        return "solomon"

    if build_attempts >= MAX_BUILD_RETRIES:
        logger.warning(
            "❌ Build failed after %d attempt(s) — giving up, moving to Solomon/Summary.",
            build_attempts,
        )
        return "solomon"

    logger.warning(
        "❌ Build failed (attempt %d/%d) → sending logs back to Critic.",
        build_attempts, MAX_BUILD_RETRIES,
    )
    return "critic"


# ── Graph construction ─────────────────────────────────────────────────────


def build_workflow() -> StateGraph:
    """Construct and compile the Vectra LangGraph workflow.

    Returns:
        A compiled ``StateGraph`` ready to be invoked with an initial state dict.
    """
    builder = StateGraph(VectraState)

    # Register all nodes
    builder.add_node("orchestrator", orchestrator_node)
    builder.add_node("critic", critic_node)
    builder.add_node("coder", coder_node)
    # Docker path nodes
    builder.add_node("docker_gen", docker_gen_node)
    builder.add_node("validation", validation_node)
    builder.add_node("solomon", solomon_node)
    # Vercel path nodes
    builder.add_node("vercel_setup", vercel_setup_node)
    builder.add_node("vercel_deploy", vercel_deploy_node)
    # Shared
    builder.add_node("summary", summary_node)

    # ── Edges ──────────────────────────────────────────────────────────
    # START → Orchestrator
    builder.add_edge(START, "orchestrator")

    # Orchestrator → Critic (first analysis pass)
    builder.add_edge("orchestrator", "critic")

    # Critic → Coder (always – the coder decides whether to patch or skip)
    builder.add_edge("critic", "coder")

    # Coder → conditional: loop back to Critic OR proceed to deploy routing
    builder.add_conditional_edges(
        "coder",
        should_continue_fixing,
        {
            "critic": "critic",
            "deploy_route": "deploy_route",
        },
    )

    # ── Deployment routing (Docker vs Vercel) ──────────────────────────
    builder.add_node("deploy_route", lambda state: {})  # pass-through
    builder.add_conditional_edges(
        "deploy_route",
        should_deploy_docker_or_vercel,
        {
            "docker_gen": "docker_gen",
            "vercel_setup": "vercel_setup",
        },
    )

    # ── Docker deployment path ─────────────────────────────────────────
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

    # ── Vercel deployment path ─────────────────────────────────────────
    # Vercel setup → Vercel deploy
    builder.add_edge("vercel_setup", "vercel_deploy")

    # Vercel deploy → Summary
    builder.add_edge("vercel_deploy", "summary")

    # Summary → END
    builder.add_edge("summary", END)

    # Compile
    workflow = builder.compile()
    logger.info("LangGraph workflow compiled successfully.")
    return workflow


def _detect_deploy_target(deploy_prompt: str) -> str:
    """Infer the deployment target from the user's prompt.

    Scans for Vercel-related keywords.  Defaults to ``"docker"``.
    """
    vercel_keywords = {
        "vercel", "serverless", "cloud function", "edge function",
        "vercel deploy", "serverless function",
    }
    prompt_lower = deploy_prompt.lower()
    for kw in vercel_keywords:
        if kw in prompt_lower:
            return "vercel"
    return "docker"


def run_workflow(
    repo_path: str,
    deploy_prompt: str = "Deploy this project securely via Docker.",
    max_iterations: int = 3,
    deploy_target: str | None = None,
) -> VectraState:
    """Build and invoke the workflow end-to-end.

    Args:
        repo_path:      Absolute path to the target repository.
        deploy_prompt:  User intent / deployment instructions.
        max_iterations: Max Critic↔Coder loop iterations.
        deploy_target:  Explicit target (``"docker"`` or ``"vercel"``).
                        If ``None``, auto-detected from ``deploy_prompt``.

    Returns:
        The final state dict after the workflow completes.
    """
    resolved_target = deploy_target or _detect_deploy_target(deploy_prompt)
    logger.info("🎯 Deployment target: %s", resolved_target)

    workflow = build_workflow()

    initial_state: VectraState = {
        "repo_path": repo_path,
        "deploy_prompt": deploy_prompt,
        "deploy_target": resolved_target,
        "codebase": "",
        "file_manifest": {},
        "plan": "",
        "issues": [],
        "current_issues": [],
        "patches": [],
        "last_patch_count": 0,
        "iteration": 0,
        "max_iterations": max_iterations,
        "build_attempts": 0,
        "dockerfile": "",
        "dockerignore": "",
        "docker_build_log": "",
        "docker_run_log": "",
        "docker_status": "",
        "vercel_json": "",
        "vercel_deploy_url": "",
        "vercel_deploy_log": "",
        "vercel_status": "",
        "logs": "[Vectra] Workflow started.",
        "summary": "",
    }

    logger.info("🚀 Starting Vectra workflow for %s", repo_path)
    final_state = workflow.invoke(initial_state)

    final_status = (
        final_state.get("vercel_status", "unknown")
        if resolved_target == "vercel"
        else final_state.get("docker_status", "unknown")
    )
    logger.info("🏁 Workflow complete. Deploy status: %s", final_status)

    return final_state
