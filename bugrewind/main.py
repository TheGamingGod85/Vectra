"""
BugRewind — CLI Entry Point.

Provides a command-line interface to run the BugRewind multi-agent workflow
without going through MCP.  Useful for development, testing, and direct
invocation.

Usage:
    uv run python -m bugrewind.main <repo_path> [--prompt "..."] [--max-iter N]
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from bugrewind.graph.workflow import run_workflow


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="bugrewind",
        description="BugRewind - AI-powered secure deployment system",
    )
    parser.add_argument(
        "repo_path",
        help="Absolute path to the target repository to scan and deploy.",
    )
    parser.add_argument(
        "--prompt",
        default="Deploy this project securely via Docker.",
        help="Deployment intent / instructions for the agents.",
    )
    parser.add_argument(
        "--max-iter",
        type=int,
        default=3,
        help="Maximum Critic-Coder loop iterations (default: 3).",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable DEBUG-level logging.",
    )

    args = parser.parse_args()

    # ── Logging setup ──────────────────────────────────────────────────
    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s [%(name)s] %(levelname)s — %(message)s",
    )

    repo = Path(args.repo_path).resolve()
    if not repo.is_dir():
        print(f"❌ Error: {repo} is not a valid directory.", file=sys.stderr)
        sys.exit(1)

    print(f"\n🚀 BugRewind starting for: {repo}")
    print(f"   Prompt:         {args.prompt}")
    print(f"   Max iterations: {args.max_iter}")
    print()

    # ── Run the workflow ───────────────────────────────────────────────
    final_state = run_workflow(
        repo_path=str(repo),
        deploy_prompt=args.prompt,
        max_iterations=args.max_iter,
    )

    # ── Print the summary ──────────────────────────────────────────────
    summary = final_state.get("summary", "")
    if summary:
        print("\n" + "=" * 72)
        print(summary)
        print("=" * 72)
    else:
        print("⚠️  No summary was generated.")

    docker_status = final_state.get("docker_status", "unknown")
    if docker_status == "deployed":
        print("\n✅ Deployment successful!  Container is running.")
        sys.exit(0)
    elif docker_status in ("build_failed", "run_failed"):
        print(f"\n❌ Deployment failed (status: {docker_status}).")
        sys.exit(1)
    else:
        print(f"\nℹ️  Final docker status: {docker_status}")
        sys.exit(0)


if __name__ == "__main__":
    main()
