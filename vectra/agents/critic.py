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
import re

from vectra.graph.state import VectraState
from vectra.utils.llm import call_ollama

logger = logging.getLogger(__name__)

# ── Static pre-scan patterns ────────────────────────────────────────────────
# These regex patterns catch common vulnerabilities that LLMs sometimes miss.
# Each tuple: (pattern, category, severity, description)
STATIC_PATTERNS: list[tuple[re.Pattern, str, str, str]] = [
    (
        re.compile(
            r"""(?:password|passwd|secret|api_?key|token|auth)\s*=\s*["'][^"']{3,}["']""",
            re.IGNORECASE,
        ),
        "Hardcoded Secret",
        "critical",
        "Hardcoded credential or secret found. Use environment variables instead.",
    ),
    (
        re.compile(
            r"""(?:DB_PASSWORD|DATABASE_URL|SECRET_KEY|JWT_SECRET|API_KEY|AWS_SECRET)\s*=\s*["'][^"']+["']""",
            re.IGNORECASE,
        ),
        "Hardcoded Environment Variable",
        "critical",
        "Sensitive environment variable is hardcoded instead of being loaded from .env or OS environment.",
    ),
    (
        re.compile(
            r"""os\.environ\s*\[\s*["'][^"']+["']\s*\]""",
        ),
        "Unsafe Env Access",
        "low",
        "Using os.environ[] without .get() — will crash if the variable is not set.",
    ),
    (
        re.compile(
            r"""subprocess\.(?:call|run|Popen)\s*\(\s*(?:f["']|["'].*\{|.*\+\s*(?:input|request))""",
            re.IGNORECASE,
        ),
        "Command Injection",
        "critical",
        "Shell command built from user input or f-string without sanitisation.",
    ),
    (
        re.compile(
            r"""(?:execute|cursor\.execute)\s*\(\s*(?:f["']|["'].*%s|.*\.format\(|.*\+\s*)""",
            re.IGNORECASE,
        ),
        "SQL Injection",
        "critical",
        "SQL query built via string concatenation/formatting instead of parameterised queries.",
    ),
    (
        re.compile(
            r"""open\s*\(\s*(?:request\.|f["']|.*\+\s*(?:input|request|user))""",
            re.IGNORECASE,
        ),
        "Path Traversal",
        "high",
        "File opened using unsanitised user input — potential path traversal.",
    ),
    (
        re.compile(
            r"""\b(?:hashlib\s*\.\s*)?(?:md5|sha1)\s*\(""",
            re.IGNORECASE,
        ),
        "Weak Hashing",
        "high",
        "Using weak hash algorithm (MD5/SHA1) — use bcrypt/argon2 for passwords, SHA-256+ for integrity.",
    ),
    (
        re.compile(
            r"""\.password\s*==\s*|==\s*.*\.password""",
        ),
        "Plaintext Password Comparison",
        "critical",
        "Direct string comparison of passwords instead of using a secure hash comparison.",
    ),
    (
        re.compile(
            r"""\bdebug\s*=\s*True\b""",
            re.IGNORECASE,
        ),
        "Debug Mode Enabled",
        "high",
        "Debug mode is enabled — must be disabled in production.",
    ),
    (
        re.compile(
            r"""CORS.*\*|allow_origins\s*=\s*\[?\s*["']\*["']""",
            re.IGNORECASE,
        ),
        "Permissive CORS",
        "high",
        "CORS allows all origins (*) — restrict to specific domains in production.",
    ),
    (
        re.compile(
            r"""(?:verify\s*=\s*False|VERIFY_SSL\s*=\s*False)""",
            re.IGNORECASE,
        ),
        "SSL Verification Disabled",
        "high",
        "SSL certificate verification is disabled — vulnerable to MITM attacks.",
    ),
]

# Files to skip during static scan (test files, configs, etc.)
STATIC_SCAN_SKIP_PATTERNS = re.compile(
    r"(?:test_|_test\.|\.test\.|spec\.|__pycache__|node_modules|\.lock$|\.md$)",
    re.IGNORECASE,
)


def _static_prescan(file_manifest: dict[str, str]) -> list[dict]:
    """Run regex-based static analysis across all source files.

    Returns a list of issue dicts in the same format the LLM produces.
    """
    issues: list[dict] = []
    issue_id = 1

    for fpath, content in sorted(file_manifest.items()):
        # Skip test / non-code files
        if STATIC_SCAN_SKIP_PATTERNS.search(fpath):
            continue

        for pattern, category, severity, description in STATIC_PATTERNS:
            for match in pattern.finditer(content):
                # Extract a snippet: the matching line ± 1 line of context
                line_start = content.rfind("\n", 0, match.start()) + 1
                line_end = content.find("\n", match.end())
                if line_end == -1:
                    line_end = len(content)
                snippet = content[line_start:line_end].strip()

                # Avoid duplicate issues for the same pattern in the same file
                already_exists = any(
                    i.get("file") == fpath
                    and i.get("category") == category
                    and i.get("snippet", "").strip() == snippet
                    for i in issues
                )
                if already_exists:
                    continue

                issues.append({
                    "id": issue_id,
                    "severity": severity,
                    "category": category,
                    "file": fpath,
                    "snippet": snippet[:200],
                    "description": description,
                    "recommendation": f"Fix the {category.lower()} issue in {fpath}.",
                    "source": "static_scan",
                })
                issue_id += 1

    return issues


CRITIC_PROMPT = """\
You are Vectra's Critic Agent — a ruthless, thorough application security auditor and code optimizer.

You are given:
1. The execution plan from the Orchestrator.
2. The full codebase of the target project.
3. Any previous patches that have been applied.
4. Issues already found by a static scanner (your job is to find ADDITIONAL issues the scanner missed).

IMPORTANT RULES:
- Look for security issues: hardcoded secrets/passwords, SQL injection, path traversal, XSS, CSRF, command injection,
  insecure deserialization, plaintext password storage, missing input validation, debug mode left on,
  permissive CORS, missing rate limiting, insecure dependencies, missing HTTPS enforcement,
  improper error handling that leaks stack traces, and missing authentication/authorization checks.
- Look for unoptimized code: unnecessary loops, blocking I/O in async endpoints, redundant database queries, O(n^2) algorithms where O(n log n) is better, memory leaks, and unnecessarily large dependencies.
- Report ONLY issues you can point to in the actual code, with the exact file and snippet.
  Do NOT invent issues to fill the list — if the code has no further genuine problems, return an empty array [].
- Every false positive costs a patching round and risks breaking working code, so be precise.

For each finding, output a JSON object with these keys:
  - "id": sequential integer starting at 1
  - "severity": "critical" | "high" | "medium" | "low"
  - "category": short label (e.g. "SQL Injection", "Hardcoded Secret")
  - "file": relative file path
  - "snippet": the offending code (≤ 4 lines)
  - "description": concise explanation of the vulnerability
  - "recommendation": how to fix it

Output a JSON array of these objects. Output ONLY the JSON array, no prose, no markdown fences.

--- PLAN ---
{plan}

--- CODEBASE ---
{codebase}

--- PREVIOUS PATCHES APPLIED ---
{patches}

--- ISSUES ALREADY FOUND BY STATIC SCANNER ---
{static_issues}

Find additional issues the static scanner missed. Output ONLY a JSON array:
"""


def _parse_issues(raw: str) -> list[dict]:
    """Best-effort parse of the LLM's issue list.

    The model should return a JSON array, but we handle common failures:
    - Leading/trailing prose around the JSON
    - Individual JSON objects separated by newlines
    - Markdown code fences wrapping the JSON
    """
    raw = raw.strip()

    if not raw:
        logger.warning("Critic LLM returned empty response — no issues parsed from LLM.")
        return []

    # Strip markdown code fences if present
    if raw.startswith("```"):
        lines = raw.splitlines()
        # Remove first line (```json or ```)
        lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        raw = "\n".join(lines).strip()

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


def _deduplicate_issues(
    static_issues: list[dict],
    llm_issues: list[dict],
) -> list[dict]:
    """Merge static and LLM issues, removing duplicates.

    Two issues are considered duplicates only if they share the same file,
    category, AND code snippet — two distinct SQL injections in the same
    file must both survive, or the Coder is never told about the second.
    """
    seen: set[tuple[str, str, str]] = set()
    merged: list[dict] = []

    for issue in static_issues + llm_issues:
        key = (
            issue.get("file", "").lower(),
            issue.get("category", "").lower(),
            " ".join(issue.get("snippet", "").split())[:120].lower(),
        )
        if key not in seen:
            seen.add(key)
            merged.append(issue)

    # Re-number IDs
    for i, issue in enumerate(merged, 1):
        issue["id"] = i

    return merged


def critic_node(state: VectraState) -> dict:
    """LangGraph node: Critic.

    Analyses the codebase using a two-phase approach:
    1. Static regex-based pre-scan for common vulnerability patterns.
    2. LLM-based deep analysis for issues the static scanner can't catch.

    Returns accumulated issues from both phases.
    """
    plan = state.get("plan", "")
    codebase = state.get("codebase", "")
    file_manifest = state.get("file_manifest", {})
    patches = state.get("patches", [])
    iteration = state.get("iteration", 0)

    # ── Phase 1: Static pre-scan ──────────────────────────────────────────
    static_issues: list[dict] = []
    if iteration == 0 and file_manifest:
        static_issues = _static_prescan(file_manifest)
        logger.info(
            "🔍 Critic static pre-scan: found %d issue(s).", len(static_issues)
        )

    # ── Phase 2: LLM deep analysis ────────────────────────────────────────
    # Include docker build/run logs if we're in a validation-retry loop
    docker_logs = ""
    if state.get("docker_build_log"):
        docker_logs += f"\n--- DOCKER BUILD LOG ---\n{state['docker_build_log']}"
    if state.get("docker_run_log"):
        docker_logs += f"\n--- DOCKER RUN LOG ---\n{state['docker_run_log']}"

    patches_text = json.dumps(patches, indent=2) if patches else "None"
    static_issues_text = (
        json.dumps(static_issues, indent=2) if static_issues else "None"
    )

    codebase_slice = codebase[:30_000]
    if len(codebase) > 30_000:
        logger.warning(
            "⚠️  Codebase is %d chars but only the first 30,000 are sent to the "
            "LLM — files beyond that point are NOT scanned by the LLM pass "
            "(the static pre-scan still covers everything).",
            len(codebase),
        )
        codebase_slice += "\n\n[NOTE: codebase truncated — additional files were not included]"

    prompt = CRITIC_PROMPT.format(
        plan=plan,
        codebase=codebase_slice,
        patches=patches_text[:5_000],
        static_issues=static_issues_text[:5_000],
    )
    if docker_logs:
        prompt += docker_logs[:5_000]

    logger.info("🔍 Critic (iteration %d): LLM scanning for issues …", iteration)

    llm_issues: list[dict] = []
    try:
        raw = call_ollama(prompt, max_tokens=8192, json_mode=True)

        # Log the raw response length for debugging
        logger.debug("Critic LLM raw response length: %d chars", len(raw))
        if not raw:
            logger.warning("⚠️  Critic LLM returned EMPTY response — relying on static scan only.")

        llm_issues = _parse_issues(raw)
        logger.info("🔍 Critic LLM found %d additional issue(s).", len(llm_issues))
    except Exception as exc:
        logger.error(
            "⚠️  Critic LLM call FAILED: %s — proceeding with static scan results only.",
            exc,
        )

    # ── Merge & deduplicate ───────────────────────────────────────────────
    all_issues = _deduplicate_issues(static_issues, llm_issues)

    log_entry = (
        f"[Critic][iter={iteration}] "
        f"Static: {len(static_issues)}, LLM: {len(llm_issues)}, "
        f"Total (deduped): {len(all_issues)} issue(s)."
    )
    logger.info(log_entry)

    return {
        "issues": all_issues,          # Annotated[list, operator.add] → appended
        "current_issues": all_issues,  # Latest batch only (overwritten, not accumulated)
        "iteration": iteration,        # unchanged here; coder increments
        "logs": state.get("logs", "") + "\n" + log_entry,
    }
