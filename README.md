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

## RewindWatcher (Background Monitoring)

RewindWatcher is a standalone background daemon that monitors containers deployed by BugRewind. If a container crashes, it automatically triggers a post-mortem AI diagnostics workflow.

### Start Monitoring
```bash
# Run the monitoring daemon
python watcher/monitor.py
```

### Features
- **Health Polling**: Checks container status every 10 minutes.
- **Forensics Extraction**: Automatically collects exit codes and last 100 log lines from crashed containers.
- **AI Diagnostics**: Correlates logs to source code using a dedicated LangGraph workflow.
- **Email Notifications**: Dispatches rich HTML reports with fix recommendations (requires `SMTP_USER` and `SMTP_APP_PASSWORD`).

