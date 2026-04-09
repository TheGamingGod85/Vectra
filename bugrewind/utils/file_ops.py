"""
BugRewind File Operations Utility.

Handles reading an entire repository into a structured manifest,
writing patches back to disk, and generating the final summary file.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)

# Extensions we consider "source code" worth scanning
SOURCE_EXTENSIONS: set[str] = {
    ".py", ".js", ".ts", ".jsx", ".tsx", ".java", ".go", ".rs",
    ".c", ".cpp", ".h", ".hpp", ".cs", ".rb", ".php", ".sh",
    ".bash", ".yml", ".yaml", ".toml", ".json", ".env", ".cfg",
    ".ini", ".sql", ".html", ".css", ".dockerfile", ".tf",
    ".hcl", ".md", ".txt", ".xml", ".conf",
}

# Files that are always interesting regardless of extension
INTERESTING_FILENAMES: set[str] = {
    "Dockerfile", "docker-compose.yml", "docker-compose.yaml",
    "Makefile", "Procfile", ".env", ".env.example",
    "requirements.txt", "Pipfile", "setup.py", "setup.cfg",
    "pyproject.toml", "package.json", "go.mod", "Cargo.toml",
    "Gemfile", "pom.xml", "build.gradle",
}

# Directories to skip
SKIP_DIRS: set[str] = {
    ".git", "__pycache__", "node_modules", ".venv", "venv",
    ".tox", ".mypy_cache", ".pytest_cache", "dist", "build",
    ".eggs", "*.egg-info",
}

MAX_FILE_SIZE = 100_000  # bytes – skip huge generated files


def read_repo(repo_path: str) -> dict[str, str]:
    """Walk the repository tree and return a dict mapping relative paths to
    file contents.

    Only text-like source files are included (see ``SOURCE_EXTENSIONS`` and
    ``INTERESTING_FILENAMES``).  Binary files, huge files, and common junk
    directories are skipped.

    Args:
        repo_path: Absolute or relative path to the repository root.

    Returns:
        ``{relative_path: file_content, ...}``
    """
    root = Path(repo_path).resolve()
    manifest: dict[str, str] = {}

    if not root.is_dir():
        logger.error("repo_path %s is not a directory", root)
        return manifest

    for dirpath, dirnames, filenames in os.walk(root):
        # Prune unwanted directories in-place
        dirnames[:] = [
            d for d in dirnames
            if d not in SKIP_DIRS and not d.endswith(".egg-info")
        ]

        for fname in filenames:
            fpath = Path(dirpath) / fname
            rel = fpath.relative_to(root).as_posix()

            # Check if file is interesting
            ext = fpath.suffix.lower()
            if ext not in SOURCE_EXTENSIONS and fname not in INTERESTING_FILENAMES:
                continue

            # Skip oversized files
            try:
                if fpath.stat().st_size > MAX_FILE_SIZE:
                    logger.debug("Skipping oversized file: %s", rel)
                    continue
            except OSError:
                continue

            try:
                content = fpath.read_text(encoding="utf-8", errors="replace")
                manifest[rel] = content
            except Exception as exc:
                logger.warning("Could not read %s: %s", rel, exc)

    logger.info("Read %d files from %s", len(manifest), root)
    return manifest


def build_codebase_text(manifest: dict[str, str]) -> str:
    """Flatten a file manifest into a single text blob suitable for LLM
    context windows.

    Each file is wrapped with clear markers::

        === FILE: path/to/file.py ===
        <content>
        === END FILE ===

    Args:
        manifest: Dict from ``read_repo()``.

    Returns:
        A single concatenated string.
    """
    parts: list[str] = []
    for path in sorted(manifest):
        parts.append(f"=== FILE: {path} ===")
        parts.append(manifest[path])
        parts.append("=== END FILE ===\n")
    return "\n".join(parts)


def apply_patch(repo_path: str, file_path: str, new_content: str) -> None:
    """Overwrite (or create) a file in the repository with new content.

    Parent directories are created as needed.

    Args:
        repo_path:   Absolute path to the repo root.
        file_path:   Relative path (posix-style) within the repo.
        new_content: Full replacement content for the file.
    """
    target = Path(repo_path) / file_path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(new_content, encoding="utf-8")
    logger.info("Patched file: %s", file_path)


def write_summary(repo_path: str, summary_md: str) -> str:
    """Write the final summary markdown to both the BugRewind ``outputs/``
    directory AND the target repository root.

    Returns:
        Absolute path to the summary file inside the target repository.
    """
    # ── Write to BugRewind's own outputs directory ────────────────────────
    out_dir = Path(__file__).resolve().parent.parent / "outputs"
    out_dir.mkdir(parents=True, exist_ok=True)
    internal_path = out_dir / "summary.md"
    internal_path.write_text(summary_md, encoding="utf-8")
    logger.info("Summary written to %s", internal_path)

    # ── Write to the target repository root ───────────────────────────────
    repo_summary_path = Path(repo_path) / "BUGREWIND_SUMMARY.md"
    try:
        repo_summary_path.write_text(summary_md, encoding="utf-8")
        logger.info("Summary also written to %s", repo_summary_path)
    except OSError as exc:
        logger.warning("Could not write summary to target repo: %s", exc)

    return str(repo_summary_path)
