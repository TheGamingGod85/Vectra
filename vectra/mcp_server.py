"""
Vectra MCP Server.

Exposes the entire Vectra multi-agent workflow as a single MCP tool
using FastMCP.  Any MCP-compatible client (Claude Desktop, Gemini, etc.)
can call ``orchestrator_tool`` to scan, fix, and deploy a local repo.
"""

from __future__ import annotations

import logging
import sys
import os

# Force silence for potentially noisy libraries
os.environ["FASTMCP_LOG_LEVEL"] = "ERROR"

from fastmcp import FastMCP
from vectra.graph.workflow import run_workflow

# Configure logging to strictly use stderr
logging.basicConfig(
    level=logging.ERROR,  # Higher level to be safe
    format="%(asctime)s [%(name)s] %(levelname)s — %(message)s",
    stream=sys.stderr,
)
logger = logging.getLogger(__name__)

# Initialize FastMCP
mcp = FastMCP(name="Vectra")


@mcp.tool
def orchestrator_tool(repo_path: str, deploy_prompt: str, target_email: str = "") -> str:
    """Run the full Vectra pipeline on a local repository.

    This tool:
    1. Initialises the LangGraph multi-agent workflow.
    2. Scans the codebase for vulnerabilities and quality issues.
    3. Iteratively applies targeted fixes (Critic ↔ Coder loop).
    4. Generates Dockerfile and .dockerignore.
    5. Builds and validates the Docker image.
    6. Deploys the container locally.
    7. Returns a markdown summary of everything that happened.

    Args:
        repo_path:     Absolute path to the target repository on disk.
        deploy_prompt: Free-form deployment instructions / user intent,
                       e.g. "Deploy this FastAPI app with security hardening".
        target_email:  Optional recipient for Sentinel crash alerts
                       (falls back to the VECTRA_TARGET_EMAIL env var).

    Returns:
        A markdown summary including issues found, patches applied,
        Docker status, and the final deployment result.
    """
    logger.info("MCP orchestrator_tool called: repo=%s", repo_path)

    try:
        final_state = run_workflow(
            repo_path=repo_path,
            deploy_prompt=deploy_prompt,
            max_iterations=3,
            target_email=target_email,
        )
        return final_state.get("summary", "No summary generated.")
    except Exception as exc:
        logger.exception("Workflow failed")
        return f"❌ Vectra workflow failed:\n\n{exc}"


def run_server() -> None:
    """Entry point for ``vectra-mcp`` console script."""
    logger.info("Starting Vectra MCP server …")
    mcp.run()


if __name__ == "__main__":
    run_server()
