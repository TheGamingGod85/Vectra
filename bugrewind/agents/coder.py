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
  - Automatically detects new imports and installs missing dependencies.

Also responsible for generating Dockerfile and .dockerignore when they are
missing from the project.
"""

from __future__ import annotations

import json
import logging
import os
import re
import subprocess
from pathlib import Path

from bugrewind.graph.state import BugRewindState
from bugrewind.utils.llm import call_ollama
from bugrewind.utils.file_ops import apply_patch, build_codebase_text

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

8. **When you add new imports** (e.g. `import bcrypt`, `from dotenv import load_dotenv`),
   you MUST also include a patch for the project's dependency file:
   - For Python with `requirements.txt`: add the new package to requirements.txt
   - For Python with `pyproject.toml`: add the new package to the dependencies
   - For Node.js: add to package.json dependencies

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


# ── Well-known Python import → pip package mapping ──────────────────────────
# Only includes cases where the import name differs from the pip package name.
IMPORT_TO_PACKAGE: dict[str, str] = {
    "dotenv": "python-dotenv",
    "cv2": "opencv-python",
    "PIL": "Pillow",
    "sklearn": "scikit-learn",
    "yaml": "pyyaml",
    "bs4": "beautifulsoup4",
    "jose": "python-jose",
    "jwt": "PyJWT",
    "Crypto": "pycryptodome",
    "passlib": "passlib",
    "bcrypt": "bcrypt",
    "argon2": "argon2-cffi",
}

# Stdlib modules to skip (not exhaustive, but covers the common false positives)
PYTHON_STDLIB: set[str] = {
    "os", "sys", "re", "json", "logging", "pathlib", "datetime", "time",
    "hashlib", "hmac", "secrets", "base64", "uuid", "collections",
    "functools", "itertools", "typing", "dataclasses", "abc", "io",
    "math", "random", "string", "textwrap", "copy", "enum", "contextlib",
    "subprocess", "shutil", "tempfile", "glob", "fnmatch", "stat",
    "threading", "multiprocessing", "concurrent", "asyncio", "socket",
    "http", "urllib", "email", "html", "xml", "csv", "sqlite3",
    "unittest", "doctest", "pdb", "traceback", "warnings", "argparse",
    "configparser", "struct", "codecs", "binascii", "operator",
    "decimal", "fractions", "statistics", "array", "queue", "heapq",
    "bisect", "weakref", "types", "inspect", "dis", "ast", "token",
    "tokenize", "pprint", "pickle", "shelve", "dbm", "gzip", "bz2",
    "zipfile", "tarfile", "lzma", "zlib", "signal", "mmap", "ctypes",
    "platform", "sysconfig", "site", "builtins", "__future__",
}


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
        return len(re.findall(r"(?:^|\n)\s*(?:def |async def |class )", content))
    elif ext in ("js", "ts", "jsx", "tsx"):
        return len(re.findall(
            r"(?:^|\n)\s*(?:function |class |const |let |var |export )",
            content,
        ))
    elif ext in ("java", "cs", "go", "rs"):
        return len(re.findall(r"(?:^|\n)\s*(?:func |fn |public |private |protected |class )", content))
    else:
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


def _extract_python_imports(content: str) -> set[str]:
    """Extract top-level Python package names from import statements.

    Returns a set of top-level package names, e.g. {'bcrypt', 'dotenv', 'fastapi'}.
    """
    packages: set[str] = set()

    # Match: import foo, import foo.bar, import foo as bar
    for m in re.finditer(r"^\s*import\s+([\w.]+)", content, re.MULTILINE):
        top = m.group(1).split(".")[0]
        packages.add(top)

    # Match: from foo import bar, from foo.bar import baz
    for m in re.finditer(r"^\s*from\s+([\w.]+)\s+import", content, re.MULTILINE):
        top = m.group(1).split(".")[0]
        packages.add(top)

    # Remove stdlib
    packages -= PYTHON_STDLIB

    return packages


def _detect_new_imports(
    old_manifest: dict[str, str],
    new_manifest: dict[str, str],
) -> set[str]:
    """Compare old and new manifests to find newly introduced Python imports.

    Returns a set of top-level package names that are new (not in the original code).
    """
    old_imports: set[str] = set()
    new_imports: set[str] = set()

    for fpath, content in old_manifest.items():
        if fpath.endswith(".py"):
            old_imports |= _extract_python_imports(content)

    for fpath, content in new_manifest.items():
        if fpath.endswith(".py"):
            new_imports |= _extract_python_imports(content)

    return new_imports - old_imports


def _detect_package_manager(repo_path: str) -> str:
    """Detect the package manager used by the target repo.

    Returns one of: 'uv', 'pip', 'pipenv', 'poetry', 'npm', 'yarn', 'unknown'.
    """
    root = Path(repo_path)

    # Python package managers
    if (root / "pyproject.toml").exists():
        pyproject = (root / "pyproject.toml").read_text(encoding="utf-8", errors="replace")
        if "[tool.poetry]" in pyproject:
            return "poetry"
        # Check if uv is available
        try:
            result = subprocess.run(
                ["uv", "--version"], capture_output=True, text=True, timeout=5
            )
            if result.returncode == 0:
                return "uv"
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass
        return "pip"  # fallback for pyproject.toml without poetry

    if (root / "Pipfile").exists():
        return "pipenv"

    if (root / "requirements.txt").exists():
        # Check if uv is available
        try:
            result = subprocess.run(
                ["uv", "--version"], capture_output=True, text=True, timeout=5
            )
            if result.returncode == 0:
                return "uv"
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass
        return "pip"

    # JavaScript package managers
    if (root / "yarn.lock").exists():
        return "yarn"
    if (root / "package.json").exists():
        return "npm"

    return "unknown"


def _install_dependencies(
    repo_path: str,
    packages: set[str],
    file_manifest: dict[str, str],
) -> tuple[list[str], str]:
    """Install newly introduced packages in the target repo.

    Detects the package manager and runs the appropriate install command.
    Also updates the dependency file (requirements.txt) if needed.

    Args:
        repo_path:      Absolute path to the repo root.
        packages:        Set of top-level Python import names to install.
        file_manifest:  Current file manifest (may be updated in place).

    Returns:
        (installed_packages, log_text)
    """
    if not packages:
        return [], ""

    # Map import names to pip package names
    pip_names: list[str] = []
    for pkg in sorted(packages):
        pip_name = IMPORT_TO_PACKAGE.get(pkg, pkg)
        pip_names.append(pip_name)

    pkg_manager = _detect_package_manager(repo_path)
    logger.info("📦 Detected package manager: %s", pkg_manager)
    logger.info("📦 New packages to install: %s", ", ".join(pip_names))

    log_lines: list[str] = []
    installed: list[str] = []

    if pkg_manager == "uv":
        # Use `uv add` for each package
        for pkg_name in pip_names:
            cmd = ["uv", "add", pkg_name]
            logger.info("Running: %s in %s", " ".join(cmd), repo_path)
            try:
                result = subprocess.run(
                    cmd,
                    cwd=repo_path,
                    capture_output=True,
                    text=True,
                    timeout=120,
                )
                if result.returncode == 0:
                    installed.append(pkg_name)
                    log_lines.append(f"  ✅ uv add {pkg_name}")
                    logger.info("✅ uv add %s succeeded", pkg_name)
                else:
                    log_lines.append(
                        f"  ⚠️ uv add {pkg_name} failed: {result.stderr[:200]}"
                    )
                    logger.warning("⚠️ uv add %s failed: %s", pkg_name, result.stderr[:200])
            except (subprocess.TimeoutExpired, FileNotFoundError) as exc:
                log_lines.append(f"  ⚠️ uv add {pkg_name} error: {exc}")
                logger.warning("⚠️ uv add %s error: %s", pkg_name, exc)

    elif pkg_manager in ("pip", "unknown"):
        # Update requirements.txt (or create it)
        req_path = Path(repo_path) / "requirements.txt"
        existing_reqs = ""
        if req_path.exists():
            existing_reqs = req_path.read_text(encoding="utf-8", errors="replace")

        # Parse existing package names (lowercase, strip version specs)
        existing_names: set[str] = set()
        for line in existing_reqs.splitlines():
            line = line.strip()
            if line and not line.startswith("#"):
                name = re.split(r"[>=<!\[]", line)[0].strip().lower()
                existing_names.add(name)

        new_entries: list[str] = []
        for pkg_name in pip_names:
            if pkg_name.lower() not in existing_names:
                new_entries.append(pkg_name)
                installed.append(pkg_name)

        if new_entries:
            updated_reqs = existing_reqs.rstrip("\n")
            if updated_reqs:
                updated_reqs += "\n"
            updated_reqs += "\n".join(new_entries) + "\n"
            req_path.write_text(updated_reqs, encoding="utf-8")
            file_manifest["requirements.txt"] = updated_reqs
            log_lines.append(
                f"  ✅ Added to requirements.txt: {', '.join(new_entries)}"
            )
            logger.info("✅ Added to requirements.txt: %s", ", ".join(new_entries))

        # Also try pip install if possible
        if new_entries:
            cmd = ["pip", "install"] + new_entries
            logger.info("Running: %s in %s", " ".join(cmd), repo_path)
            try:
                subprocess.run(
                    cmd,
                    cwd=repo_path,
                    capture_output=True,
                    text=True,
                    timeout=120,
                )
            except (subprocess.TimeoutExpired, FileNotFoundError):
                pass  # Non-critical, Docker will install from requirements.txt

    elif pkg_manager == "poetry":
        for pkg_name in pip_names:
            cmd = ["poetry", "add", pkg_name]
            logger.info("Running: %s in %s", " ".join(cmd), repo_path)
            try:
                result = subprocess.run(
                    cmd, cwd=repo_path, capture_output=True, text=True, timeout=120,
                )
                if result.returncode == 0:
                    installed.append(pkg_name)
                    log_lines.append(f"  ✅ poetry add {pkg_name}")
                else:
                    log_lines.append(f"  ⚠️ poetry add {pkg_name} failed")
            except (subprocess.TimeoutExpired, FileNotFoundError) as exc:
                log_lines.append(f"  ⚠️ poetry add {pkg_name} error: {exc}")

    log_text = "\n".join(log_lines) if log_lines else ""
    return installed, log_text


def coder_node(state: BugRewindState) -> dict:
    """LangGraph node: Coder.

    Reads critic issues, generates patches, validates them, writes to disk,
    and auto-installs any new dependencies introduced by the patches.
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

    # Save a snapshot of the current manifest for import diffing
    old_manifest = dict(file_manifest)

    # Only fix the issues from the current iteration (last batch)
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

    # ── Auto-detect and install new dependencies ──────────────────────────
    new_imports = _detect_new_imports(old_manifest, file_manifest)
    dep_log = ""
    if new_imports:
        logger.info("📦 Detected new imports: %s", ", ".join(sorted(new_imports)))
        installed, dep_log = _install_dependencies(repo_path, new_imports, file_manifest)
        if installed:
            logger.info("📦 Installed %d new package(s).", len(installed))

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
    if dep_log:
        log_parts.append(f"[Coder] Dependency install:\n{dep_log}")

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
