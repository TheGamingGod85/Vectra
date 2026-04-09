"""
Coder Agent – LangGraph Node.

Receives the Critic's findings and applies targeted fixes to the codebase.
Key constraint: does NOT rewrite the entire repository — only patches the
specific files and code sections flagged by the Critic.

Also responsible for generating Dockerfile and .dockerignore when they are
missing from the project.
"""

from __future__ import annotations

import json
import logging

from bugrewind.graph.state import BugRewindState
from bugrewind.utils.llm import call_ollama
from bugrewind.utils.file_ops import apply_patch, build_codebase_text

logger = logging.getLogger(__name__)

CODER_FIX_PROMPT = """\
You are BugRewind's Coder Agent — a senior software engineer.

You are given a list of security/quality issues found by the Critic, along with
the relevant source files.  Your job is to produce MINIMAL, TARGETED patches
that fix each issue WITHOUT rewriting the entire repository.

For each fix, output a JSON object with:
  - "file": the relative file path to patch
  - "description": what was changed and why
  - "new_content": the COMPLETE new content of the file after fixes

Output a JSON array of these fix objects.  Output ONLY valid JSON, nothing else.

--- ISSUES TO FIX ---
{issues}

--- RELEVANT SOURCE FILES ---
{relevant_files}

--- PATCHES (JSON array) ---
"""

DOCKERFILE_PROMPT = """\
You are BugRewind's Coder Agent.  Generate a minimal, production-ready
Dockerfile for the following project.

Requirements:
- Use a slim/alpine base image where possible
- Do NOT run as root (create a non-root user)
- Pin the base image version
- Copy only necessary files
- Install dependencies properly
- Set a proper ENTRYPOINT or CMD
- Expose the correct port if it's a web app

--- PROJECT SUMMARY ---
{plan}

--- KEY FILES ---
{key_files}

Output ONLY the Dockerfile content, no markdown fences, no explanation.
"""

DOCKERIGNORE_PROMPT = """\
Generate a .dockerignore file for a project with these files:
{file_list}

Include standard ignores (.git, __pycache__, node_modules, .env, venv, etc.)
and anything else that should not be in a Docker image.

Output ONLY the .dockerignore content, nothing else.
"""


def _parse_patches(raw: str) -> list[dict]:
    """Parse the Coder's patch output, tolerating common LLM quirks."""
    raw = raw.strip()

    try:
        data = json.loads(raw)
        if isinstance(data, list):
            return data
        if isinstance(data, dict):
            for v in data.values():
                if isinstance(v, list):
                    return v
            return [data]
    except json.JSONDecodeError:
        pass

    start = raw.find("[")
    end = raw.rfind("]")
    if start != -1 and end != -1 and end > start:
        try:
            return json.loads(raw[start : end + 1])
        except json.JSONDecodeError:
            pass

    return []


def _get_relevant_files(
    file_manifest: dict[str, str],
    issues: list[dict],
) -> str:
    """Extract only the source files mentioned in the issues list."""
    files_needed: set[str] = set()
    for issue in issues:
        f = issue.get("file", "")
        if f and f in file_manifest:
            files_needed.add(f)

    # If no specific files matched, return all (fallback)
    if not files_needed:
        files_needed = set(file_manifest.keys())

    parts: list[str] = []
    for path in sorted(files_needed):
        content = file_manifest[path]
        parts.append(f"=== FILE: {path} ===")
        parts.append(content)
        parts.append("=== END FILE ===\n")
    return "\n".join(parts)


def coder_node(state: BugRewindState) -> dict:
    """LangGraph node: Coder.

    Reads critic issues, generates patches, and writes them to disk.
    Increments the iteration counter.
    """
    issues = state.get("issues", [])
    file_manifest = state.get("file_manifest", {})
    repo_path = state["repo_path"]
    iteration = state.get("iteration", 0)

    if not issues:
        log_entry = "[Coder] No issues to fix.  Skipping."
        logger.info(log_entry)
        return {
            "patches": [],
            "iteration": iteration + 1,
            "logs": state.get("logs", "") + "\n" + log_entry,
        }

    # Only fix the issues from the current iteration (last batch)
    # Since issues accumulate via operator.add, take the latest batch:
    # we use a heuristic – issues added in this pass have higher IDs or
    # are beyond the count we saw in the previous iteration.
    current_issues = issues  # in practice, we pass all; LLM deduplicates

    relevant_src = _get_relevant_files(file_manifest, current_issues)

    prompt = CODER_FIX_PROMPT.format(
        issues=json.dumps(current_issues, indent=2)[:10_000],
        relevant_files=relevant_src[:25_000],
    )

    logger.info("🔧 Coder (iteration %d): generating patches for %d issue(s) …",
                iteration, len(current_issues))
    raw = call_ollama(prompt)
    patches = _parse_patches(raw)

    # Apply patches to disk
    applied_patches: list[dict] = []
    for patch in patches:
        fpath = patch.get("file", "")
        new_content = patch.get("new_content", "")
        desc = patch.get("description", "")

        if not fpath or not new_content:
            logger.warning("Skipping incomplete patch: %s", patch)
            continue

        apply_patch(repo_path, fpath, new_content)

        # Update the in-memory manifest so subsequent nodes see the fix
        file_manifest[fpath] = new_content

        applied_patches.append({
            "file": fpath,
            "description": desc,
            "iteration": iteration,
        })

    # Rebuild codebase text after patching
    new_codebase = build_codebase_text(file_manifest)

    log_entry = (
        f"[Coder][iter={iteration}] Applied {len(applied_patches)} patch(es)."
    )
    logger.info(log_entry)

    return {
        "patches": applied_patches,
        "file_manifest": file_manifest,
        "codebase": new_codebase,
        "iteration": iteration + 1,
        "logs": state.get("logs", "") + "\n" + log_entry,
    }


def docker_gen_node(state: BugRewindState) -> dict:
    """LangGraph node: Docker Generation.

    Generates Dockerfile and .dockerignore if they don't already exist in the
    target repo.  Also writes them to disk.
    """
    repo_path = state["repo_path"]
    plan = state.get("plan", "")
    file_manifest = state.get("file_manifest", {})

    logs = state.get("logs", "")

    # ── Dockerfile ─────────────────────────────────────────────────────────
    existing_dockerfile = file_manifest.get("Dockerfile", "")
    if existing_dockerfile and "FROM" in existing_dockerfile:
        logger.info("📦 Dockerfile already exists, keeping it.")
        dockerfile = existing_dockerfile
    else:
        key_files = "\n".join(
            f"- {p}" for p in sorted(file_manifest.keys())[:30]
        )
        prompt = DOCKERFILE_PROMPT.format(plan=plan, key_files=key_files)
        logger.info("📦 Docker Gen: generating Dockerfile …")
        dockerfile = call_ollama(prompt)

        # Strip markdown fences the LLM sometimes adds
        dockerfile = dockerfile.strip()
        if dockerfile.startswith("```"):
            lines = dockerfile.splitlines()
            dockerfile = "\n".join(lines[1:])
        if dockerfile.endswith("```"):
            dockerfile = dockerfile[: -len("```")].strip()

        apply_patch(repo_path, "Dockerfile", dockerfile)
        logs += "\n[DockerGen] Generated Dockerfile."

    # ── .dockerignore ──────────────────────────────────────────────────────
    existing_dockerignore = file_manifest.get(".dockerignore", "")
    if existing_dockerignore:
        dockerignore = existing_dockerignore
    else:
        file_list = "\n".join(sorted(file_manifest.keys())[:50])
        prompt = DOCKERIGNORE_PROMPT.format(file_list=file_list)
        logger.info("📦 Docker Gen: generating .dockerignore …")
        dockerignore = call_ollama(prompt)

        dockerignore = dockerignore.strip()
        if dockerignore.startswith("```"):
            lines = dockerignore.splitlines()
            dockerignore = "\n".join(lines[1:])
        if dockerignore.endswith("```"):
            dockerignore = dockerignore[: -len("```")].strip()

        apply_patch(repo_path, ".dockerignore", dockerignore)
        logs += "\n[DockerGen] Generated .dockerignore."

    return {
        "dockerfile": dockerfile,
        "dockerignore": dockerignore,
        "logs": logs,
    }
