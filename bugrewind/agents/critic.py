"""
Critic Agent – LangGraph Node.

Security and quality reviewer.  Scans the full codebase for:

* Hard-coded secrets / API keys
* Unsafe shell usage (subprocess without sanitisation)
* Dependency risks (unpinned versions, known risky packages)
* Missing Dockerfile / deployment configs
* SQL injection, path traversal, XSS, and other OWASP-style flaws
* Plaintext password storage
* Missing input validation

Outputs a structured list of findings with severity, description, file, and
relevant code snippet.
"""

from __future__ import annotations

import json
import logging

from bugrewind.graph.state import BugRewindState
from bugrewind.utils.llm import call_ollama

logger = logging.getLogger(__name__)

CRITIC_PROMPT = """\
You are BugRewind's Critic Agent — a ruthless application security auditor.

You are given:
1. The execution plan from the Orchestrator.
2. The full codebase of the target project.
3. Any previous patches that have been applied.

Your mission: find ALL security vulnerabilities, quality issues, and deployment
gaps.  Be thorough but precise — every finding MUST reference a specific file
and include a short code snippet.

For each finding, output a JSON object on its own line with these keys:
  - "id": sequential integer starting at 1
  - "severity": "critical" | "high" | "medium" | "low"
  - "category": short label (e.g. "SQL Injection", "Hardcoded Secret")
  - "file": relative file path
  - "snippet": the offending code (≤ 4 lines)
  - "description": concise explanation of the vulnerability
  - "recommendation": how to fix it

Output a JSON array of these objects.  Output ONLY the JSON array, nothing else.

If there are no remaining issues, output an empty JSON array: []

--- PLAN ---
{plan}

--- CODEBASE ---
{codebase}

--- PREVIOUS PATCHES APPLIED ---
{patches}

--- FINDINGS (JSON array) ---
"""


def _parse_issues(raw: str) -> list[dict]:
    """Best-effort parse of the LLM's issue list.

    The model should return a JSON array, but we handle common failures:
    - Leading/trailing prose around the JSON
    - Individual JSON objects separated by newlines
    """
    raw = raw.strip()

    # Try direct parse first
    try:
        data = json.loads(raw)
        if isinstance(data, list):
            return data
        if isinstance(data, dict):
            # Sometimes the model wraps the array in a key
            for v in data.values():
                if isinstance(v, list):
                    return v
            return [data]
    except json.JSONDecodeError:
        pass

    # Try to extract the first JSON array from the text
    start = raw.find("[")
    end = raw.rfind("]")
    if start != -1 and end != -1 and end > start:
        try:
            return json.loads(raw[start : end + 1])
        except json.JSONDecodeError:
            pass

    # Last resort: try to parse line by line
    issues: list[dict] = []
    for line in raw.splitlines():
        line = line.strip().rstrip(",")
        if line.startswith("{"):
            try:
                issues.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return issues


def critic_node(state: BugRewindState) -> dict:
    """LangGraph node: Critic.

    Analyses the codebase and returns accumulated issues.
    """
    plan = state.get("plan", "")
    codebase = state.get("codebase", "")
    patches = state.get("patches", [])
    iteration = state.get("iteration", 0)

    # Include docker build/run logs if we're in a validation-retry loop
    docker_logs = ""
    if state.get("docker_build_log"):
        docker_logs += f"\n--- DOCKER BUILD LOG ---\n{state['docker_build_log']}"
    if state.get("docker_run_log"):
        docker_logs += f"\n--- DOCKER RUN LOG ---\n{state['docker_run_log']}"

    patches_text = json.dumps(patches, indent=2) if patches else "None"

    prompt = CRITIC_PROMPT.format(
        plan=plan,
        codebase=codebase[:30_000],
        patches=patches_text[:5_000],
    )
    if docker_logs:
        prompt += docker_logs[:5_000]

    logger.info("🔍 Critic (iteration %d): scanning for issues …", iteration)
    raw = call_ollama(prompt)
    issues = _parse_issues(raw)

    log_entry = f"[Critic][iter={iteration}] Found {len(issues)} issue(s)."
    logger.info(log_entry)

    return {
        "issues": issues,          # Annotated[list, operator.add] → appended
        "iteration": iteration,    # unchanged here; coder increments
        "logs": state.get("logs", "") + "\n" + log_entry,
    }
