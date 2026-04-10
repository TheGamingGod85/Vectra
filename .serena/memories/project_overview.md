# BugRewind Project Overview

## Purpose
BugRewind is an AI-powered secure deployment system using multi-agent orchestration. It analyzes codebases, detects vulnerabilities, iteratively fixes issues, generates deployment configs, validates via Docker, and deploys locally.

## Tech Stack
- **Language**: Python 3.11+
- **Package Manager**: uv
- **LLM**: Ollama API (kimi-k2.5:cloud or codellama)
- **Agent Framework**: LangGraph
- **MCP Server**: FastMCP
- **Docker**: Docker CLI (subprocess)
- **Web Dashboard**: FastAPI + React/Vite
- **Dependencies**: langgraph, langchain-core, langchain-ollama, fastmcp, httpx, pydantic, fastapi, uvicorn, websockets, python-multipart
- **Frontend**: React 18.2.0, Vite 4.4.5, lucide-react 0.284.0, react-markdown 10.1.0, remark-gfm 4.0.1

## Architecture
LangGraph-based multi-agent workflow with the following agents:

1. **Orchestrator Agent**: Entry point that understands repo + user intent, creates execution plan, creates backup of original codebase
2. **Critic Agent**: Security + quality reviewer that detects vulnerabilities (secrets, unsafe shell usage, dependency risks, missing Dockerfile, OWASP-style flaws). Uses both static regex patterns and LLM analysis.
3. **Coder Agent**: Applies fixes based on critic findings (does NOT rewrite entire repo), generates Dockerfile and .dockerignore when missing
4. **Solomon Agent**: Execution agent that runs shell commands and executes Docker (build, run, validation)

## Workflow Graph
```
START → Orchestrator → Critic → Coder → Critic (loop)
      → Docker Gen → Validation → [pass?] → Solomon → Summary → END
                                 ↘ [fail?] → Critic (re-analyse, max 2 retries)
```

The Critic-Coder loop continues until:
- No issues remain, OR
- `max_iterations` is reached, OR
- The coder is stuck (applied 0 patches with issues remaining)

After Docker build fails, the error logs are fed back to the Critic for up to 2 re-analysis attempts (MAX_BUILD_RETRIES = 2).

## State Management
Uses `BugRewindState` TypedDict with fields:
- `repo_path`: Absolute path to the target repository on disk
- `deploy_prompt`: Free-form user intent / deployment instructions
- `codebase`: Concatenated source code text ingested from the repo
- `file_manifest`: Mapping of relative file path → file content for targeted patching
- `plan`: Structured execution plan produced by the Orchestrator
- `issues`: Accumulated list of vulnerability / quality findings (uses operator.add reducer)
- `current_issues`: The LATEST batch of issues from the most recent Critic run (what Coder actually fixes)
- `patches`: Accumulated list of code patches produced by the Coder (uses operator.add reducer)
- `last_patch_count`: Number of patches successfully applied in the most recent Coder run
- `iteration`: Current critic↔coder loop iteration (0-indexed)
- `max_iterations`: Upper bound on how many critic↔coder loops to run
- `build_attempts`: Number of Docker build attempts so far (capped at MAX_BUILD_RETRIES)
- `dockerfile`: Generated Dockerfile content
- `dockerignore`: Generated .dockerignore content
- `docker_build_log`: Stdout/stderr from `docker build`
- `docker_run_log`: Stdout/stderr from `docker run`
- `docker_status`: High-level status string, e.g. "success", "build_failed"
- `logs`: Human-readable running log of all agent activity
- `summary`: Final markdown summary written to outputs/summary.md

Issues and patches use `operator.add` reducer for accumulation.

## Project Structure
```
bugrewind/
├── main.py              # CLI entry point
├── mcp_server.py        # MCP server entry point
├── dashboard_api.py     # FastAPI backend for dashboard
├── gui.py               # GUI launcher (starts backend + frontend)
├── graph/
│   ├── state.py         # BugRewindState TypedDict
│   └── workflow.py      # LangGraph workflow definition
├── agents/
│   ├── orchestrator.py  # Entry point agent
│   ├── critic.py        # Security/quality reviewer (static patterns + LLM)
│   ├── coder.py         # Applies fixes, generates Docker configs
│   └── solomon.py       # Execution agent (Docker)
├── tools/
│   └── docker_tools.py  # Docker CLI wrappers
├── utils/
│   ├── llm.py           # Ollama API wrapper
│   └── file_ops.py      # File operations (read_repo, apply_patch, create_backup)
├── dashboard/           # React/Vite frontend
│   ├── package.json
│   ├── vite.config.js
│   └── src/
│       ├── App.jsx
│       ├── main.jsx
│       └── index.css
└── outputs/
    └── summary.md       # Generated summary
```

## Key Design Patterns
- Each agent is a distinct LangGraph node
- State travels through the entire workflow
- Clear separation of responsibilities
- Iterative improvement loop between Critic and Coder
- Docker validation before final deployment
- Build failure retry mechanism (max 2 retries)
- WebSocket-based real-time dashboard updates
- FastAPI backend with CORS for local development
- React/Vite frontend for visualization with markdown rendering support
- Static pattern scanning for common vulnerabilities in Critic agent
- Backup creation before any code modifications

## Entry Points
1. **Interactive Launcher**: `start.py` - Menu-driven interface for choosing between:
   - GUI Dashboard (Interactive Web UI)
   - CLI Automation (Headless terminal scan)
   - MCP Server (Protocol for AI Assistants)
   - Exit

2. **CLI**: `bugrewind.main` - Command-line interface for direct workflow execution
   ```bash
   uv run python -m bugrewind.main /path/to/repo --prompt "Deploy securely"
   ```

3. **MCP Server**: `bugrewind.mcp_server` - Exposes workflow as MCP tool for AI assistants
   ```bash
   uv run python -m bugrewind.mcp_server
   ```

4. **Dashboard API**: `bugrewind.dashboard_api` - FastAPI server with WebSocket support
   ```bash
   uv run uvicorn bugrewind.dashboard_api:app --reload
   ```

5. **GUI Launcher**: `bugrewind.gui` - Starts both backend (FastAPI) and frontend (Vite) concurrently
   ```bash
   uv run python -m bugrewind.gui
   ```

## Dashboard Architecture
- **Backend**: FastAPI server running on port 8000
  - `/health` - Health check endpoint
  - `/ws` - WebSocket endpoint for real-time updates
  - `/api/run` - POST endpoint to trigger workflow runs
- **Frontend**: React/Vite dev server running on port 3000
  - Uses lucide-react for icons
  - Uses react-markdown and remark-gfm for markdown rendering
  - Connects to backend via WebSocket for live updates

## Critic Agent Static Pattern Scanning
The Critic agent uses static regex patterns to catch common vulnerabilities that LLMs sometimes miss:
- Hardcoded secrets/passwords/API keys
- Hardcoded environment variables (DB_PASSWORD, SECRET_KEY, etc.)
- Unsafe subprocess calls without shell sanitization
- SQL injection patterns
- Path traversal patterns
- XSS vulnerabilities
- Plaintext password storage

## Installed Scripts
After `uv sync`, the following scripts are available:
- `bugrewind` - Runs the CLI entry point
- `bugrewind-mcp` - Runs the MCP server

## Output Files
- `outputs/summary.md` - Generated markdown summary of the entire workflow execution
- `.env` - Created by Coder agent when hardcoded secrets are found
- `Dockerfile` - Generated if missing
- `.dockerignore` - Generated if missing
- Backup directory - Created by Orchestrator before any modifications
