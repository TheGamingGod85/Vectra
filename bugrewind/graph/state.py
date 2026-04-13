"""
BugRewind Graph State Definition.

Defines the central TypedDict state object that flows through every node
in the LangGraph workflow. Every agent reads from and writes to this
shared state, ensuring structured inter-agent communication.
"""

from __future__ import annotations

import operator
from typing import Annotated, TypedDict


class BugRewindState(TypedDict):
    """Shared state that travels through the entire LangGraph workflow.

    Attributes:
        repo_path:          Absolute path to the target repository on disk.
        deploy_prompt:      Free-form user intent / deployment instructions.
        deploy_target:      Deployment backend — ``"docker"`` (default) or ``"vercel"``.
                            Determined automatically from the deploy_prompt.
        codebase:           Concatenated source code text ingested from the repo.
        file_manifest:      Mapping of relative file path → file content for
                            targeted patching by the Coder agent.
        plan:               Structured execution plan produced by the Orchestrator.
        issues:             Accumulated list of vulnerability / quality findings
                            produced by the Critic (uses operator.add reducer so
                            successive runs append rather than overwrite).
        current_issues:     The LATEST batch of issues from the most recent Critic run.
                            This is what the Coder actually fixes — not the full
                            accumulated history.
        patches:            Accumulated list of code patches produced by the Coder
                            (also uses operator.add reducer).
        last_patch_count:   Number of patches successfully applied in the most recent
                            Coder run.  Used by routing to detect "stuck" loops.
        iteration:          Current critic↔coder loop iteration (0-indexed).
        max_iterations:     Upper bound on how many critic↔coder loops to run.
        build_attempts:     Number of Docker build attempts so far.  Used to cap
                            the build-fail → critic retry loop.
        dockerfile:         Generated Dockerfile content.
        dockerignore:       Generated .dockerignore content.
        docker_build_log:   Stdout/stderr from `docker build`.
        docker_run_log:     Stdout/stderr from `docker run`.
        docker_status:      High-level status string, e.g. "success", "build_failed".
        vercel_json:        Generated vercel.json content.
        vercel_deploy_url:  The URL returned by ``vercel deploy``.
        vercel_deploy_log:  Stdout/stderr from the Vercel CLI.
        vercel_status:      High-level status string, e.g. "deployed", "deploy_failed".
        kubernetes_manifests: Generated Kubernetes YAML manifests.
        kubernetes_deploy_log: Stdout/stderr from kubectl apply.
        kubernetes_status:  High-level status string, e.g. "deployed", "deploy_failed".
        logs:               Human-readable running log of all agent activity.
        summary:            Final markdown summary written to outputs/summary.md.
    """

    repo_path: str
    deploy_prompt: str
    deploy_target: str
    codebase: str
    file_manifest: dict[str, str]
    plan: str
    issues: Annotated[list[dict], operator.add]
    current_issues: list[dict]
    patches: Annotated[list[dict], operator.add]
    last_patch_count: int
    iteration: int
    max_iterations: int
    build_attempts: int
    dockerfile: str
    dockerignore: str
    docker_build_log: str
    docker_run_log: str
    docker_status: str
    vercel_json: str
    vercel_deploy_url: str
    vercel_deploy_log: str
    vercel_status: str
    kubernetes_manifests: str
    kubernetes_deploy_log: str
    kubernetes_status: str
    logs: str
    summary: str
