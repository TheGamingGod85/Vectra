"""
Solomon Agent – LangGraph Node.

The execution agent.  Solomon is the ONLY agent allowed to:

* Run shell commands
* Execute Docker builds and container starts

It orchestrates the validation step: build → run → check.  If the build or
run fails, it feeds the error logs back into state so the Critic can
re-analyse and the Coder can re-patch.
"""

from __future__ import annotations

import logging

from bugrewind.graph.state import BugRewindState
from bugrewind.tools.docker_tools import docker_build, docker_run

logger = logging.getLogger(__name__)


def validation_node(state: BugRewindState) -> dict:
    """LangGraph node: Validation.

    Runs ``docker build`` against the target repo.  Does NOT start the
    container yet — that's Solomon's job after validation passes.
    """
    repo_path = state["repo_path"]
    logs = state.get("logs", "")

    logger.info("🧪 Validation: building Docker image …")

    success, build_log = docker_build(context_path=repo_path)

    status = "build_success" if success else "build_failed"
    log_entry = f"[Validation] docker build → {status}"
    logger.info(log_entry)

    return {
        "docker_build_log": build_log,
        "docker_status": status,
        "logs": logs + "\n" + log_entry,
    }


def solomon_node(state: BugRewindState) -> dict:
    """LangGraph node: Solomon (Execution).

    If the Docker image was built successfully, Solomon starts the container
    and performs a basic health-check.  This is the final deployment step.
    """
    logs = state.get("logs", "")

    docker_status = state.get("docker_status", "")
    if docker_status != "build_success":
        log_entry = (
            "[Solomon] Skipping deployment — build did not succeed "
            f"(status={docker_status})."
        )
        logger.warning(log_entry)
        return {
            "docker_status": "deploy_skipped",
            "logs": logs + "\n" + log_entry,
        }

    logger.info("🚀 Solomon: starting container …")
    success, run_log = docker_run()

    if success:
        status = "deployed"
        log_entry = "[Solomon] Container deployed successfully."
        logger.info("✅ " + log_entry)
    else:
        status = "run_failed"
        log_entry = f"[Solomon] Container failed to start.\n{run_log[:500]}"
        logger.error(log_entry)

    return {
        "docker_run_log": run_log,
        "docker_status": status,
        "logs": logs + "\n" + log_entry,
    }


def summary_node(state: BugRewindState) -> dict:
    """LangGraph node: Summary.

    Generates outputs/summary.md with the full run report.
    Also writes BUGREWIND_SUMMARY.md into the target repository root.
    """
    import datetime
    from bugrewind.utils.file_ops import write_summary

    issues = state.get("issues", [])
    patches = state.get("patches", [])
    iteration = state.get("iteration", 0)
    docker_status = state.get("docker_status", "unknown")
    logs = state.get("logs", "")
    repo_path = state.get("repo_path", "N/A")
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # ── Build the markdown summary ────────────────────────────────────────
    lines: list[str] = [
        "# BugRewind — Deployment Summary",
        "",
        f"**Generated:** `{timestamp}`",
        f"**Repository:** `{repo_path}`",
        f"**Iterations:** {iteration}",
        f"**Docker Status:** `{docker_status}`",
        f"**Total Issues Found:** {len(issues)}",
        f"**Total Patches Applied:** {len(patches)}",
        "",
        "---",
        "",
        "## Issues Found",
        "",
    ]

    if issues:
        # Group by severity for better readability
        for sev_label in ("critical", "high", "medium", "low"):
            sev_issues = [i for i in issues if i.get("severity", "").lower() == sev_label]
            if sev_issues:
                lines.append(f"### {sev_label.upper()} ({len(sev_issues)})")
                lines.append("")
                for issue in sev_issues:
                    cat = issue.get("category", "General")
                    fpath = issue.get("file", "?")
                    desc = issue.get("description", "")
                    source = issue.get("source", "llm")
                    source_badge = " 🔬" if source == "static_scan" else " 🤖"
                    lines.append(f"- **[{cat}]** `{fpath}`{source_badge}")
                    lines.append(f"  - {desc}")
                    snippet = issue.get("snippet", "")
                    if snippet:
                        lines.append(f"  - ```\n  {snippet}\n  ```")
                    rec = issue.get("recommendation", "")
                    if rec:
                        lines.append(f"  - **Fix:** {rec}")
                    lines.append("")
    else:
        lines.append("_No issues found._")
        lines.append("")

    lines += [
        "---",
        "",
        "## Patches Applied",
        "",
    ]

    if patches:
        for i, p in enumerate(patches, 1):
            lines.append(f"{i}. **`{p.get('file', '?')}`** — {p.get('description', 'N/A')}"
                         f" (iteration {p.get('iteration', '?')})")
    else:
        lines.append("_No patches applied._")

    lines += [
        "",
        "---",
        "",
        "## Docker Build Log (last 50 lines)",
        "",
        "```",
        "\n".join((state.get("docker_build_log", "") or "N/A").splitlines()[-50:]),
        "```",
        "",
        "## Docker Run Log (last 30 lines)",
        "",
        "```",
        "\n".join((state.get("docker_run_log", "") or "N/A").splitlines()[-30:]),
        "```",
        "",
        "---",
        "",
        "## Agent Activity Log",
        "",
        "```",
        logs,
        "```",
        "",
        "---",
        "",
        "## Final Result",
        "",
    ]

    if docker_status == "deployed":
        lines.append("✅ **Deployment succeeded.**  Container is running.")
    elif docker_status == "build_success":
        lines.append("⚠️ **Build succeeded** but container was not started.")
    elif docker_status == "build_failed":
        lines.append("❌ **Docker build failed.**  See logs above.")
    elif docker_status == "run_failed":
        lines.append("❌ **Container failed to start.**  See logs above.")
    else:
        lines.append(f"ℹ️ Docker status: `{docker_status}`")

    lines.append("")
    lines.append("---")
    lines.append("*Generated by [BugRewind](https://github.com/TheGamingGod85/BugRewind) 🐛⏪*")

    summary_md = "\n".join(lines)
    summary_path = write_summary(repo_path, summary_md)

    log_entry = f"[Summary] Report written to {summary_path}"
    logger.info(log_entry)

    return {
        "summary": summary_md,
        "logs": state.get("logs", "") + "\n" + log_entry,
    }
