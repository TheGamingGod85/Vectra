"""
Coder Agent – LangGraph Node.

Receives the Critic's findings and applies targeted fixes to the codebase.
Key constraints:
  - Does NOT rewrite the entire repository — only patches the specific files
    and code sections flagged by the Critic.
  - NEVER deletes functionality — only replaces insecure code with secure
    equivalents.
  - For hardcoded secrets/env vars, creates a .env file and updates the code
    to read from environment variables.

Also responsible for generating Dockerfile and .dockerignore when they are
missing from the project.
"""

from __future__ import annotations

import json
import logging
import re

from bugrewind.graph.state import BugRewindState
from bugrewind.utils.llm import call_ollama
from bugrewind.utils.file_ops import apply_patch, build_codebase_text, create_backup

logger = logging.getLogger(__name__)

# ── Prompt: Fix Issues ─────────────────────────────────────────────────────

CODER_FIX_PROMPT = """\
You are BugRewind's Coder Agent — a senior software engineer who writes SECURE code.

You are given a list of security/quality issues found by the Critic, along with
the relevant source files.  Your job is to produce MINIMAL, TARGETED patches
that fix each issue.

## CRITICAL RULES — READ CAREFULLY:

1. **NEVER DELETE CODE OR FUNCTIONALITY.**  You must REPLACE insecure code with
   secure equivalents.  Every feature, endpoint, function, and variable that
   existed before MUST still exist after your fix.  If a function had a SQL
   injection bug, fix the SQL query — do NOT delete the function.

2. **For hardcoded secrets, passwords, API keys, database URLs, or any
   sensitive values:**
   - Move them to a `.env` file (create one if it doesn't exist).
   - Update the source code to read from environment variables using
     `os.environ.get("VAR_NAME")` (Python) or `process.env.VAR_NAME` (JS/TS)
     or the language-appropriate equivalent.
   - Include a separate entry for the `.env` file in your output.

3. **For SQL injection:** Replace string formatting/concatenation with
   parameterised queries.  Keep the SAME query logic.

4. **For plaintext password storage:** Add proper hashing (bcrypt/argon2).
   Keep the same authentication flow.

5. **For missing input validation:** ADD validation — do not remove the
   endpoint or function.

6. **The patched file must be a COMPLETE, WORKING file.**  Include ALL imports,
   ALL functions, ALL classes — not just the changed parts.  The file must be
   ready to drop in and run.

7. **The patched file MUST have the same number of functions/classes/endpoints
   as the original, or MORE (never fewer).**

## Output Format

For each fix, output a JSON object with:
  - "file": the relative file path to patch
  - "description": what was changed and why (be specific)
  - "new_content": the COMPLETE new content of the file after fixes

If you need to create a `.env` file, include an entry with "file": ".env"
and "new_content" containing all the extracted secrets in KEY=value format.

If you need to create a `.env.example` file (with placeholder values), include
that too.

Output a JSON array of these fix objects.  Output ONLY valid JSON, nothing else.
No markdown fences, no prose before or after.

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
- If a .env file exists, do NOT copy it into the image (use runtime env vars)

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

    if not raw:
        return []

    # Strip markdown code fences if present
    if raw.startswith("```"):
        lines = raw.splitlines()
        lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        raw = "\n".join(lines).strip()

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


def _count_definitions(content: str, file_path: str) -> int:
    """Rough count of top-level definitions (functions, classes, routes) in a file.

    Used to sanity-check that the LLM didn't delete functionality.
    """
    ext = file_path.rsplit(".", 1)[-1].lower() if "." in file_path else ""

    if ext == "py":
        # Count def/class/async def at module level or indented
        return len(re.findall(r"(?:^|\n)\s*(?:def |async def |class )", content))
    elif ext in ("js", "ts", "jsx", "tsx"):
        # Count function/class/const/let/var with arrow or function keyword
        return len(re.findall(
            r"(?:^|\n)\s*(?:function |class |const |let |var |export )",
            content,
        ))
    elif ext in ("java", "cs", "go", "rs"):
        return len(re.findall(r"(?:^|\n)\s*(?:func |fn |public |private |protected |class )", content))
    else:
        # For unknown languages, skip validation
        return -1


def _validate_patch(
    original_content: str | None,
    new_content: str,
    file_path: str,
) -> tuple[bool, str]:
    """Validate that a patch doesn't delete functionality.

    Returns:
        (is_valid, reason)
    """
    # New files (like .env) are always valid
    if original_content is None:
        return True, "new file"

    # Check the patched file isn't (much) smaller than the original
    original_lines = original_content.count("\n") + 1
    new_lines = new_content.count("\n") + 1
    if new_lines < original_lines * 0.5:
        return False, (
            f"Patch reduced file from {original_lines} to {new_lines} lines "
            f"(>{50}% reduction) — likely deleted code"
        )

    # Check definition count didn't decrease
    orig_defs = _count_definitions(original_content, file_path)
    new_defs = _count_definitions(new_content, file_path)
    if orig_defs > 0 and new_defs >= 0 and new_defs < orig_defs:
        return False, (
            f"Patch reduced definitions from {orig_defs} to {new_defs} — "
            f"likely deleted functions/classes"
        )

    # Check the new content isn't almost empty
    if len(new_content.strip()) < 20:
        return False, "Patch content is nearly empty"

    return True, "ok"


def coder_node(state: BugRewindState) -> dict:
    """LangGraph node: Coder.

    Reads critic issues, generates patches, validates them, and writes to disk.
    Creates a backup of the original files before any modifications.
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

    # ── Create backup before patching ─────────────────────────────────────
    backup_path = create_backup(repo_path, file_manifest)
    logger.info("📂 Backup at: %s", backup_path)

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

    # Apply patches to disk (with validation)
    applied_patches: list[dict] = []
    rejected_patches: list[dict] = []

    for patch in patches:
        fpath = patch.get("file", "")
        new_content = patch.get("new_content", "")
        desc = patch.get("description", "")

        if not fpath or not new_content:
            logger.warning("Skipping incomplete patch: %s", patch)
            continue

        # ── Validate the patch ────────────────────────────────────────────
        original = file_manifest.get(fpath)  # None for new files like .env
        is_valid, reason = _validate_patch(original, new_content, fpath)

        if not is_valid:
            logger.warning(
                "❌ REJECTED patch for %s: %s — keeping original file intact.",
                fpath, reason,
            )
            rejected_patches.append({
                "file": fpath,
                "description": desc,
                "rejected_reason": reason,
                "iteration": iteration,
            })
            continue

        # ── Apply the patch ───────────────────────────────────────────────
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

    log_parts = [
        f"[Coder][iter={iteration}] Applied {len(applied_patches)} patch(es).",
    ]
    if rejected_patches:
        log_parts.append(
            f"  Rejected {len(rejected_patches)} patch(es) that would have deleted code."
        )
        for rp in rejected_patches:
            log_parts.append(f"    ✘ {rp['file']}: {rp['rejected_reason']}")

    log_entry = "\n".join(log_parts)
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
