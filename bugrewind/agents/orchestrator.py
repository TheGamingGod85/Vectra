"""
Orchestrator Agent – LangGraph Node.

Entry point of the Vectra workflow.  Responsibilities:

1. Read and understand the target repository.
2. Create a backup of the original codebase before any changes.
3. Interpret the user's deployment intent.
4. Produce a structured execution plan for downstream agents.
"""

from __future__ import annotations

import logging

from vectra.graph.state import VectraState
from vectra.utils.file_ops import read_repo, build_codebase_text, create_backup
from vectra.utils.llm import call_ollama

logger = logging.getLogger(__name__)

ORCHESTRATOR_PROMPT = """\
You are Vectra's Orchestrator Agent — a senior DevSecOps architect.

You have been given the full source code of a repository, a deployment request
from the user, and a deployment target.  Your job is to:

1. Summarise the project: language/framework, purpose, entry points.
2. Identify what deployment artefacts are needed based on the DEPLOY TARGET:
   - If the target is **docker**: plan for Dockerfile, .dockerignore, and container deployment.
   - If the target is **vercel**: plan for vercel.json, requirements.txt, and Vercel
     Serverless Function deployment.  The FastAPI app must be accessible via an
     ``api/`` directory entry point (e.g. ``api/main.py``).  Note any restructuring
     needed to make the project compatible with Vercel's Python runtime.
3. List the areas of concern the Critic agent should focus on (secrets, unsafe
   shell usage, dependency risks, missing configs, etc.).
4. Produce a numbered execution plan that the downstream Critic and Coder agents
   will follow.

Be concise.  Output ONLY the plan, no preamble.

--- USER REQUEST ---
{deploy_prompt}

--- DEPLOY TARGET ---
{deploy_target}

--- CODEBASE ---
{codebase}

--- PLAN ---
"""


def orchestrator_node(state: VectraState) -> dict:
    """LangGraph node: Orchestrator.

    Reads the repo, creates a backup, builds the codebase context, calls the
    LLM to produce an execution plan, and populates the shared state.
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

    # ── Step 2: Create a backup of the original codebase ───────────────────
    backup_path = create_backup(repo_path, file_manifest)
    logger.info("📂 Backup of original codebase at: %s", backup_path)

    # ── Step 3: Ask the LLM for an execution plan ─────────────────────────
    deploy_target = state.get("deploy_target", "docker")
    prompt = ORCHESTRATOR_PROMPT.format(
        deploy_prompt=deploy_prompt,
        deploy_target=deploy_target,
        codebase=codebase[:30_000],  # cap to avoid blowing the context window
    )

    logger.info("🎯 Orchestrator: generating execution plan …")
    plan = call_ollama(prompt)

    log_entry = (
        f"[Orchestrator] Ingested {len(file_manifest)} files. "
        f"Backup at {backup_path}. "
        f"Plan length: {len(plan)} chars."
    )
    logger.info(log_entry)

    return {
        "codebase": codebase,
        "file_manifest": file_manifest,
        "plan": plan,
        "logs": state.get("logs", "") + "\n" + log_entry,
    }
