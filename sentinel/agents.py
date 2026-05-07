"""
Sentinel Post-Mortem Agent Nodes.

Contains the PM Critic and PM Coder LangGraph nodes that perform
post-mortem analysis on crashed containers.  Both nodes reuse the
same Ollama / LLM abstraction layer from ``vectra.utils.llm``
to ensure model consistency.
"""

from __future__ import annotations

import logging
from pathlib import Path

from vectra.utils.llm import call_ollama
from vectra.utils.file_ops import read_repo, build_codebase_text

from sentinel.state import WatcherState

logger = logging.getLogger(__name__)

# ── Prompt Templates ───────────────────────────────────────────────────────

PM_CRITIC_PROMPT = """\
You are an expert site reliability engineer performing a post-mortem analysis.

## Container Crash Details
- **Container ID**: {container_id}
- **Exit Code**: {exit_code}
- **OOM Killed**: {is_oom_killed}

## Container Logs (last 100 lines)
```
{container_logs}
```

## Source Code Context
```
{source_code_context}
```

## Instructions
Analyze the Docker logs and the provided source code carefully.
Correlate any stack traces in the logs to the exact files and line numbers in the source code.

Categorize the failure as ONE of the following:
- **infrastructure**: Missing environment variables, database unreachable, OOM killed, \
port conflicts, missing system dependencies, permission errors.
- **source_code**: Unhandled exceptions, logical errors, syntax bugs, import errors, \
type errors, missing modules in the application code.

Produce a detailed diagnostic report that includes:
1. The exact root cause of the crash.
2. The category classification (infrastructure or source_code).
3. Relevant log lines and their correlation to source code.
4. Impact assessment.

Begin your response with the category on its own line, exactly like:
CATEGORY: infrastructure
or
CATEGORY: source_code

Then provide the full diagnostic report below.
"""

PM_CODER_PROMPT = """\
You are a Senior Software Engineer reviewing a post-mortem diagnostic report \
for a crashed Docker container.

## Diagnostic Report
{diagnostic_report}

## Source Code Context
```
{source_code_context}
```

## Instructions
Based on the diagnostic report, formulate an actionable, step-by-step fix recommendation.

If the issue is in the source code:
- Provide the EXACT code changes needed, specifying the file path and line numbers.
- Show the before/after for each change.
- Format changes as markdown diff blocks.

If the issue is infrastructure-related:
- Provide the exact environment variables, configuration changes, or Docker \
  command modifications needed.
- Include example values where appropriate.

Format your recommendation beautifully for inclusion in an email report.
Use markdown formatting throughout.
Do NOT execute any changes — only describe them.
"""


def pm_critic_node(state: WatcherState) -> dict:
    """LangGraph node: Post-Mortem Critic (Root Cause Analyst).

    Analyses container logs and source code to determine the root cause
    of a container crash.  Classifies it as ``'infrastructure'`` or
    ``'source_code'`` and produces a diagnostic report.
    """
    container_id = state["container_id"]
    exit_code = state["exit_code"]
    is_oom_killed = state["is_oom_killed"]
    container_logs = state["container_logs"]
    source_code_context = state.get("source_code_context", "")

    # ── Build source context if not already provided ─────────────────────
    if not source_code_context:
        repo_path = state["repo_path"]
        try:
            file_manifest = read_repo(repo_path)
            source_code_context = build_codebase_text(file_manifest)
            # Truncate to avoid token limits
            if len(source_code_context) > 15000:
                source_code_context = source_code_context[:15000] + "\n... (truncated)"
        except Exception as exc:
            logger.warning("Failed to read repo at %s: %s", repo_path, exc)
            source_code_context = f"(Unable to read repository: {exc})"

    prompt = PM_CRITIC_PROMPT.format(
        container_id=container_id,
        exit_code=exit_code,
        is_oom_killed=is_oom_killed,
        container_logs=container_logs,
        source_code_context=source_code_context,
    )

    logger.info("🔍 PM Critic: analysing crash for container %s …", container_id)

    response = call_ollama(prompt)

    # ── Parse the category from the response ─────────────────────────────
    category = "unknown"
    lines = response.splitlines()
    for line in lines:
        stripped = line.strip().upper()
        if stripped.startswith("CATEGORY:"):
            raw_cat = stripped.split(":", 1)[1].strip().lower()
            if raw_cat in ("infrastructure", "source_code"):
                category = raw_cat
            break

    # Remove the CATEGORY line from the diagnostic report
    report_lines = [
        ln for ln in lines
        if not ln.strip().upper().startswith("CATEGORY:")
    ]
    diagnostic_report = "\n".join(report_lines).strip()

    logger.info(
        "✅ PM Critic: root cause → %s (report length=%d chars)",
        category, len(diagnostic_report),
    )

    return {
        "root_cause_category": category,
        "diagnostic_report": diagnostic_report,
        "source_code_context": source_code_context,
    }


def pm_coder_node(state: WatcherState) -> dict:
    """LangGraph node: Post-Mortem Coder (Solution Architect).

    Takes the diagnostic report and source code context to produce
    an actionable, step-by-step fix recommendation.  Does NOT apply
    any changes — only formats them for email delivery.
    """
    diagnostic_report = state["diagnostic_report"]
    source_code_context = state.get("source_code_context", "")

    prompt = PM_CODER_PROMPT.format(
        diagnostic_report=diagnostic_report,
        source_code_context=source_code_context,
    )

    logger.info("🛠️  PM Coder: generating fix recommendation …")

    fix_recommendation = call_ollama(prompt)

    logger.info(
        "✅ PM Coder: recommendation ready (%d chars)",
        len(fix_recommendation),
    )

    return {
        "fix_recommendation": fix_recommendation,
    }
