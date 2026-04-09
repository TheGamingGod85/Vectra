"""
Orchestrator Agent – LangGraph Node.

Entry point of the BugRewind workflow.  Responsibilities:

1. Read and understand the target repository.
2. Interpret the user's deployment intent.
3. Produce a structured execution plan for downstream agents.
"""

from __future__ import annotations

import logging

from bugrewind.graph.state import BugRewindState
from bugrewind.utils.file_ops import read_repo, build_codebase_text
from bugrewind.utils.llm import call_ollama

logger = logging.getLogger(__name__)

ORCHESTRATOR_PROMPT = """\
You are BugRewind's Orchestrator Agent — a senior DevSecOps architect.

You have been given the full source code of a repository and a deployment request
from the user.  Your job is to:

1. Summarise the project: language/framework, purpose, entry points.
2. Identify what deployment artefacts are needed (Dockerfile, .dockerignore, etc.).
3. List the areas of concern the Critic agent should focus on (secrets, unsafe
   shell usage, dependency risks, missing configs, etc.).
4. Produce a numbered execution plan that the downstream Critic and Coder agents
   will follow.

Be concise.  Output ONLY the plan, no preamble.

--- USER REQUEST ---
{deploy_prompt}

--- CODEBASE ---
{codebase}

--- PLAN ---
"""


def orchestrator_node(state: BugRewindState) -> dict:
    """LangGraph node: Orchestrator.

    Reads the repo, builds the codebase context, calls the LLM to produce an
    execution plan, and populates the shared state.
    """
    repo_path = state["repo_path"]
    deploy_prompt = state.get("deploy_prompt", "Deploy this project securely via Docker.")

    logger.info("🎯 Orchestrator: reading repo at %s", repo_path)

    # ── Step 1: Ingest the repository ──────────────────────────────────────
    file_manifest = read_repo(repo_path)
    codebase = build_codebase_text(file_manifest)

    if not file_manifest:
        plan = (
            "ERROR: No source files found in the repository. "
            "Please check the repo_path and try again."
        )
        logger.error(plan)
        return {
            "codebase": "",
            "file_manifest": {},
            "plan": plan,
            "logs": state.get("logs", "") + "\n[Orchestrator] " + plan,
        }

    # ── Step 2: Ask the LLM for an execution plan ─────────────────────────
    prompt = ORCHESTRATOR_PROMPT.format(
        deploy_prompt=deploy_prompt,
        codebase=codebase[:30_000],  # cap to avoid blowing the context window
    )

    logger.info("🎯 Orchestrator: generating execution plan …")
    plan = call_ollama(prompt)

    log_entry = (
        f"[Orchestrator] Ingested {len(file_manifest)} files. "
        f"Plan length: {len(plan)} chars."
    )
    logger.info(log_entry)

    return {
        "codebase": codebase,
        "file_manifest": file_manifest,
        "plan": plan,
        "logs": state.get("logs", "") + "\n" + log_entry,
    }
