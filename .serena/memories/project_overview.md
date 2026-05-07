# Vectra Project Overview

## Purpose
Vectra is an AI-powered secure deployment system using multi-agent orchestration. It analyzes codebases, detects vulnerabilities, iteratively fixes issues, generates deployment configs, validates via Docker, and deploys locally.

## Tech Stack
- **Language**: Python 3.11+
- **Package Manager**: uv
- **LLM**: Ollama API (kimi-k2.5:cloud or codellama)
- **Agent Framework**: LangGraph
- **MCP Server**: FastMCP
- **Docker**: Docker SDK (for monitoring) and Docker CLI (for deployments)
- **Database**: SQLite (for monitoring state)
- **Web Dashboard**: FastAPI + React/Vite
- **Dependencies**: langgraph, langchain-core, langchain-ollama, fastmcp, httpx, pydantic, fastapi, uvicorn, websockets, python-multipart, docker, markdown
- **Frontend Dependencies**: React, React DOM, lucide-react, react-markdown, remark-gfm, Vite

## Architecture
LangGraph-based multi-agent orchestration comprising two main services:

### 1. Vectra Deployment Service
The main workflow for securing and deploying applications.
- **Orchestrator Agent**: Entry point, creates execution plan and backups.
- **Critic Agent**: Security reviewer (static patterns + LLM).
- **Coder Agent**: Applies patches and generates Docker/Vercel configs.
- **Solomon Agent**: Execution engine (Docker/Vercel builds and runs). Now includes a hook to register successful deployments in the monitoring database.

### 2. Sentinel Monitoring Service (`watcher/`)
A standalone background daemon for post-mortem diagnostics.
- **monitor.py**: Polling loop (10-min interval) that tracks container health via Docker SDK.
- **Forensics Workflow**: Triggered upon crash detection.
    - **PM Critic Agent**: Root cause analyst (infrastructure vs. source code).
    - **PM Coder Agent**: Solution architect, formulates fix recommendations.
    - **Dispatcher**: Notifies users via rich HTML emails (SMTP).

## Deployment Targets
- **Docker**: (Default) Iterative validation loop (max 2 build retries).
- **Vercel**: Serverless deployment for FastAPI/Python projects.

## Project Structure
```
vectra/
├── main.py              # CLI entry point
├── mcp_server.py        # MCP server entry point
├── dashboard_api.py     # FastAPI backend for dashboard
├── gui.py               # GUI launcher
├── graph/               # Deployment workflow
├── agents/              # Deployment agents
├── tools/               # Subprocess wrappers (Docker/Vercel)
└── utils/               # File Ops, LLM, and DB utility
    ├── db.py            # SQLite management for monitoring

watcher/                 # Sentinel service
├── monitor.py           # Daemon entry point
├── graph.py             # Forensics workflow definition
├── agents.py            # Post-mortem analysis nodes
├── state.py             # WatcherState definition
└── notifier.py          # SMTP email dispatcher

dashboard/               # React/Vite frontend
.prompts/                # System prompt files for AI agents
├── PROMPT.md           # Main system prompt
└── REWINDPROMPT.md     # Sentinel specification
outputs/                 # Deployment summaries
monitored_containers.sqlite # Database tracking active containers
```

## Key Design Patterns
- **Decoupled Handoff**: Vectra hands off monitoring duties to Sentinel via a shared SQLite database.
- **Iterative Improvement**: Critic-Coder loop for deployments.
- **Correlated Forensics**: Watcher correlates container logs back to source code lines for precise fixes.
- **Graceful Failure**: Monitoring continues even if the LLM is temporarily unavailable.

## Entry Points
1. **Interactive Launcher**: `start.py`
2. **Vectra CLI**: `uv run python -m vectra.main`
3. **Sentinel**: `uv run python watcher/monitor.py`
4. **MCP Server**: `vectra-mcp`
