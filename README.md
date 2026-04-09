# BugRewind

AI-powered secure deployment system using multi-agent orchestration.

## Quick Start

```bash
# Install dependencies
uv sync

# Run against a target repo
uv run python -m bugrewind.main /path/to/repo --prompt "Deploy securely"

# Run as MCP server
uv run python -m bugrewind.mcp_server
```

## Prerequisites

- Python 3.11+
- [Ollama](https://ollama.ai) running locally with `kimi-k2.5:cloud` model
- Docker CLI installed and available in PATH
- uv package manager

## Architecture

LangGraph-based multi-agent workflow:

```
START → Orchestrator → Critic → Coder → Critic (loop)
      → Docker Gen → Validation → Solomon → Summary → END
```
