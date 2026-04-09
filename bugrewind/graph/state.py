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
        repo_path:        Absolute path to the target repository on disk.
        deploy_prompt:    Free-form user intent / deployment instructions.
        codebase:         Concatenated source code text ingested from the repo.
        file_manifest:    Mapping of relative file path → file content for
                          targeted patching by the Coder agent.
        plan:             Structured execution plan produced by the Orchestrator.
        issues:           Accumulated list of vulnerability / quality findings
                          produced by the Critic (uses operator.add reducer so
                          successive runs append rather than overwrite).
        patches:          Accumulated list of code patches produced by the Coder
                          (also uses operator.add reducer).
        iteration:        Current critic↔coder loop iteration (0-indexed).
        max_iterations:   Upper bound on how many critic↔coder loops to run.
        dockerfile:       Generated Dockerfile content.
        dockerignore:     Generated .dockerignore content.
        docker_build_log: Stdout/stderr from `docker build`.
        docker_run_log:   Stdout/stderr from `docker run`.
        docker_status:    High-level status string, e.g. "success", "build_failed".
        logs:             Human-readable running log of all agent activity.
        summary:          Final markdown summary written to outputs/summary.md.
    """

    repo_path: str
    deploy_prompt: str
    codebase: str
    file_manifest: dict[str, str]
    plan: str
    issues: Annotated[list[dict], operator.add]
    patches: Annotated[list[dict], operator.add]
    iteration: int
    max_iterations: int
    dockerfile: str
    dockerignore: str
    docker_build_log: str
    docker_run_log: str
    docker_status: str
    logs: str
    summary: str
