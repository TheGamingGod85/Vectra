"""
Solomon Agent – LangGraph Node.

The execution agent.  Solomon is the ONLY agent allowed to:

* Run shell commands
* Execute Docker builds and container starts
* Deploy to Vercel via the Vercel CLI

It orchestrates the validation step: build → run → check.  If the build or
run fails, it feeds the error logs back into state so the Critic can
re-analyse and the Coder can re-patch.

For Vercel deployments, Solomon generates the required configuration
(vercel.json, requirements.txt) and drives the ``vercel deploy`` CLI.
"""

from __future__ import annotations

import logging
import re
import uuid
from pathlib import Path

from vectra import config
from vectra.graph.state import VectraState
from vectra.tools.docker_tools import docker_build, docker_run, detect_exposed_port
from vectra.tools.vercel_tools import (
    vercel_generate_config,
    vercel_generate_requirements,
    vercel_deploy,
    vercel_inspect,
)

logger = logging.getLogger(__name__)


def _repo_slug(repo_path: str) -> str:
    """Derive a docker-safe slug from the target repo's directory name."""
    name = Path(repo_path).resolve().name.lower()
    slug = re.sub(r"[^a-z0-9]+", "-", name).strip("-") or "app"
    return slug[:30]


def image_tag_for(repo_path: str) -> str:
    """Deterministic per-repo image tag, so concurrent deployments of
    different repos don't overwrite each other's images."""
    return f"vectra-{_repo_slug(repo_path)}:latest"


def validation_node(state: VectraState) -> dict:
    """LangGraph node: Validation.

    Runs ``docker build`` against the target repo.  Does NOT start the
    container yet — that's Solomon's job after validation passes.
    """
    repo_path = state["repo_path"]
    logs = state.get("logs", "")
    build_attempts = state.get("build_attempts", 0) + 1

    logger.info("🧪 Validation: building Docker image (attempt %d) …", build_attempts)

    success, build_log = docker_build(
        context_path=repo_path,
        tag=image_tag_for(repo_path),
    )

    status = "build_success" if success else "build_failed"
    log_entry = f"[Validation] docker build (attempt {build_attempts}) → {status}"
    logger.info(log_entry)

    return {
        "docker_build_log": build_log,
        "docker_status": status,
        "build_attempts": build_attempts,
        "logs": logs + "\n" + log_entry,
    }


def solomon_node(state: VectraState) -> dict:
    """LangGraph node: Solomon (Execution).

    If the Docker image was built successfully, Solomon starts the container
    and performs a basic health-check.  This is the final deployment step.
    On successful deployment, the container is registered in the monitoring
    database so Sentinel can track it.
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

    repo_path = state["repo_path"]

    # ── Per-deployment identity ──────────────────────────────────────────
    slug = _repo_slug(repo_path)
    container_name = f"vectra-{slug}-{uuid.uuid4().hex[:8]}"
    tag = image_tag_for(repo_path)

    # ── Publish the port the Dockerfile EXPOSEs ──────────────────────────
    exposed_port = detect_exposed_port(state.get("dockerfile", ""))
    ports = f"{exposed_port}:{exposed_port}" if exposed_port else None

    # ── Pass extracted secrets to the container at runtime ───────────────
    # The Coder moves hardcoded secrets into .env and .dockerignore keeps it
    # out of the image, so the container must receive it via --env-file.
    env_file_path = Path(repo_path) / ".env"
    env_file = str(env_file_path) if env_file_path.exists() else None

    logger.info(
        "🚀 Solomon: starting container %s (ports=%s, env_file=%s) …",
        container_name, ports or "none", "yes" if env_file else "no",
    )
    success, run_log, container_id = docker_run(
        tag=tag,
        container_name=container_name,
        ports=ports,
        env_file=env_file,
    )

    if success:
        status = "deployed"
        log_entry = f"[Solomon] Container {container_name} deployed successfully."
        if ports:
            log_entry += f"\n[Solomon] Published on http://localhost:{exposed_port}"
        logger.info("✅ " + log_entry)

        # ── Register container for Sentinel monitoring ──────────
        try:
            from vectra.utils.db import insert_container

            record_id = str(uuid.uuid4())
            target_email = state.get("target_email") or config.TARGET_EMAIL

            insert_container(
                record_id=record_id,
                container_id=container_id or container_name,
                repository_path=repo_path,
                target_email=target_email,
            )
            log_entry += (
                f"\n[Solomon] Registered container for Sentinel monitoring "
                f"(id={record_id})."
            )
            logger.info(
                "📡 Container registered for monitoring (record_id=%s)", record_id
            )
        except Exception as exc:
            logger.warning("Could not register container for monitoring: %s", exc)
            log_entry += (
                f"\n[Solomon] Warning: failed to register for monitoring — {exc}"
            )
    else:
        status = "run_failed"
        log_entry = f"[Solomon] Container failed to start.\n{run_log[:500]}"
        logger.error(log_entry)

    return {
        "docker_run_log": run_log,
        "docker_status": status,
        "logs": logs + "\n" + log_entry,
    }


# ── Vercel deployment nodes ─────────────────────────────────────────────────


def vercel_setup_node(state: VectraState) -> dict:
    """LangGraph node: Vercel Setup.

    Generates ``vercel.json`` and ``requirements.txt`` for a FastAPI project
    so it can be deployed as a Vercel Serverless Function.

    The entry point is auto-detected from the file manifest: looks for
    ``api/main.py``, ``main.py``, ``app/main.py``, or ``api/index.py``
    in that order.
    """
    repo_path = state["repo_path"]
    file_manifest = state.get("file_manifest", {})
    logs = state.get("logs", "")

    logger.info("📦 Vercel Setup: generating configuration …")

    # ── Auto-detect the FastAPI entry point ──────────────────────────────
    candidates = ["api/main.py", "main.py", "app/main.py", "api/index.py"]
    entry_point = "api/main.py"  # default
    for candidate in candidates:
        if candidate in file_manifest:
            entry_point = candidate
            break

    # ── Generate vercel.json ───────────────────────────────────────────
    ok_config, config_log = vercel_generate_config(
        project_path=repo_path,
        entry_point=entry_point,
    )
    logs += f"\n[VercelSetup] {config_log}"

    # ── Detect extra dependencies from actual import statements ────────
    from vectra.agents.coder import _extract_python_imports

    import_map = {
        "sqlalchemy": "sqlalchemy",
        "pydantic": "pydantic",
        "httpx": "httpx",
        "jinja2": "jinja2",
        "multipart": "python-multipart",
        "aiofiles": "aiofiles",
        "databases": "databases",
        "passlib": "passlib",
        "jose": "python-jose",
        "bcrypt": "bcrypt",
        "starlette": "starlette",
    }
    used_imports: set[str] = set()
    for fpath, content in file_manifest.items():
        if fpath.endswith(".py"):
            used_imports |= _extract_python_imports(content)

    extra_deps = [
        pip_name
        for import_name, pip_name in import_map.items()
        if import_name in used_imports
    ]

    ok_reqs, reqs_log = vercel_generate_requirements(
        project_path=repo_path,
        extra_deps=extra_deps,
    )
    logs += f"\n[VercelSetup] {reqs_log}"

    # Read back the generated vercel.json for state
    import json
    from pathlib import Path
    vercel_json_path = Path(repo_path) / "vercel.json"
    vercel_json_content = ""
    if vercel_json_path.exists():
        vercel_json_content = vercel_json_path.read_text(encoding="utf-8")

    status = "setup_success" if (ok_config and ok_reqs) else "setup_failed"
    log_entry = f"[VercelSetup] Configuration generated → {status}"
    logger.info(log_entry)

    return {
        "vercel_json": vercel_json_content,
        "vercel_status": status,
        "logs": logs + "\n" + log_entry,
    }


def vercel_deploy_node(state: VectraState) -> dict:
    """LangGraph node: Vercel Deployment.

    Deploys the project to Vercel using the CLI.  If setup failed earlier,
    deployment is skipped gracefully.
    """
    repo_path = state["repo_path"]
    logs = state.get("logs", "")
    vercel_status = state.get("vercel_status", "")

    if vercel_status != "setup_success":
        log_entry = (
            "[VercelDeploy] Skipping deployment — setup did not succeed "
            f"(status={vercel_status})."
        )
        logger.warning(log_entry)
        return {
            "vercel_status": "deploy_skipped",
            "logs": logs + "\n" + log_entry,
        }

    # ── Deploy (preview by default; VECTRA_VERCEL_PROD=1 for production) ──
    env_label = "production" if config.VERCEL_PROD else "preview"
    logger.info("🚀 Vercel Deploy: deploying to %s …", env_label)
    success, deploy_log = vercel_deploy(
        project_path=repo_path,
        prod=config.VERCEL_PROD,
    )

    # Extract the deployment URL from the log
    deploy_url = ""
    if success:
        # vercel deploy prints the URL as the first non-empty line
        for line in deploy_log.splitlines():
            stripped = line.strip()
            if stripped.startswith("https://"):
                deploy_url = stripped
                break

        status = "deployed"
        log_entry = f"[VercelDeploy] Deployed successfully → {deploy_url}"
        logger.info("✅ " + log_entry)

        # Optionally inspect the deployment
        _, inspect_log = vercel_inspect(
            deployment_url=deploy_url,
            project_path=repo_path,
        )
        deploy_log += "\n\n--- Deployment Inspection ---\n" + inspect_log
    else:
        status = "deploy_failed"
        log_entry = f"[VercelDeploy] Deployment failed.\n{deploy_log[:500]}"
        logger.error(log_entry)

    return {
        "vercel_deploy_url": deploy_url,
        "vercel_deploy_log": deploy_log,
        "vercel_status": status,
        "logs": logs + "\n" + log_entry,
    }


def summary_node(state: VectraState) -> dict:
    """LangGraph node: Summary.

    Generates outputs/summary.md with the full run report.
    Also writes VECTRA_SUMMARY.md into the target repository root.
    """
    import datetime
    from vectra.utils.file_ops import write_summary

    issues = state.get("issues", [])
    patches = state.get("patches", [])
    iteration = state.get("iteration", 0)
    docker_status = state.get("docker_status", "unknown")
    deploy_target = state.get("deploy_target", "docker")
    vercel_status = state.get("vercel_status", "unknown")
    logs = state.get("logs", "")
    repo_path = state.get("repo_path", "N/A")
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # ── Build the markdown summary ────────────────────────────────────────
    lines: list[str] = [
        "# Vectra — Deployment Summary",
        "",
        f"**Generated:** `{timestamp}`",
        f"**Repository:** `{repo_path}`",
        f"**Deploy Target:** `{deploy_target}`",
        f"**Iterations:** {iteration}",
        f"**Docker Status:** `{docker_status}`" if deploy_target == "docker" else f"**Vercel Status:** `{vercel_status}`",
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

    # ── Deployment logs section (conditional on deploy target) ───────────
    if deploy_target == "vercel":
        vercel_deploy_url = state.get("vercel_deploy_url", "N/A")
        lines += [
            "## Vercel Deployment",
            "",
            f"**Deployment URL:** `{vercel_deploy_url}`",
            "",
            "### Vercel Deploy Log (last 50 lines)",
            "",
            "```",
            "\n".join((state.get("vercel_deploy_log", "") or "N/A").splitlines()[-50:]),
            "```",
            "",
        ]
    else:
        lines += [
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
        ]

    lines += [
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

    # ── Final result (conditional on deploy target) ─────────────────────
    if deploy_target == "vercel":
        if vercel_status == "deployed":
            url = state.get("vercel_deploy_url", "")
            lines.append(f"✅ **Vercel deployment succeeded.**  Live at: `{url}`")
        elif vercel_status == "setup_failed":
            lines.append("❌ **Vercel setup failed.**  See logs above.")
        elif vercel_status == "deploy_failed":
            lines.append("❌ **Vercel deployment failed.**  See logs above.")
        elif vercel_status == "deploy_skipped":
            lines.append("⚠️ **Vercel deployment was skipped.**")
        else:
            lines.append(f"ℹ️ Vercel status: `{vercel_status}`")
    else:
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
    lines.append("*Generated by [Vectra](https://github.com/TheGamingGod85/Vectra) 🐛⏪*")

    summary_md = "\n".join(lines)
    summary_path = write_summary(repo_path, summary_md)

    log_entry = f"[Summary] Report written to {summary_path}"
    logger.info(log_entry)

    return {
        "summary": summary_md,
        "logs": state.get("logs", "") + "\n" + log_entry,
    }
