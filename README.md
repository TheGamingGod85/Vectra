# Vectra

AI-powered secure deployment system using multi-agent orchestration.

[Walkthrough videos](https://youtube.com/playlist?list=PL1_dtHw-VrownpmumDZUEC2OPxwF5YXEu)

Vectra takes a repository you already have, plans how to deploy it, writes the
missing container and deployment files, builds and runs it, verifies it responds,
and hands back a summary of what it changed. A background daemon then keeps
watching the containers it deployed and runs an AI post-mortem if one dies.

## What it does

- **Multi-agent planning** — an orchestrator breaks the goal into tasks, a critic
  reviews each plan, and a coder applies the changes to the target repo.
- **Container generation** — writes a Dockerfile and `.env` when the repo lacks
  one, builds the image, publishes the declared port, and probes it over HTTP.
- **Vercel deployments** — detects frontend projects and can ship them to Vercel
  as a preview or production deployment.
- **Isolated deployments** — images are tagged per repo (`vectra-<repo>:latest`)
  and containers get unique names, so several deployments coexist.
- **Secrets stay out of images** — extracted secrets are passed with `--env-file`,
  never baked into the image.
- **Sentinel monitoring** — polls deployed containers, collects exit codes and
  logs from crashes, correlates them with source code, and emails a fix report.
- **Three entry points** — interactive dashboard, headless CLI, and MCP server.

## Prerequisites

- Python 3.11+
- [uv](https://docs.astral.sh/uv/)
- [Ollama](https://ollama.ai) reachable at `VECTRA_OLLAMA_URL`
- Docker CLI on `PATH` (required even when deploying to Vercel — builds run in Docker)
- Bun or Node, only if you want to run the dashboard frontend

## Quick start

```bash
uv sync
uv run python start.py                 # menu: dashboard / CLI / MCP
uv run python -m vectra.main /path/to/repo --prompt "Deploy securely"
uv run python -m vectra.mcp_server     # MCP server on stdio
```

`start.py` is the launcher; each mode can also be run directly:

| Mode | Command | Notes |
|---|---|---|
| Dashboard | `uv run python -m vectra.gui` | FastAPI on `:8000` + Vite on `:3000` |
| CLI | `uv run python -m vectra.main <repo> [--prompt ...] [--email ...]` | headless, prints the run |
| MCP server | `uv run python -m vectra.mcp_server` | exposes `orchestrator_tool` |
| Sentinel | `uv run python sentinel/monitor.py` | background container monitor |

The dashboard installs its own dependencies on first start (`vectra/dashboard`).

## Configuration

Every tunable lives in `vectra/config.py` and is read from the environment once at
import time. No credentials are hardcoded.

| Variable | Default | Purpose |
|---|---|---|
| `VECTRA_OLLAMA_URL` | `http://localhost:11434/api/generate` | Ollama generate endpoint |
| `VECTRA_OLLAMA_MODEL` | `minimax-m3:cloud` | Model tag used by all agents |
| `VECTRA_LLM_TIMEOUT` | `500` | LLM request timeout (seconds) |
| `VECTRA_TARGET_EMAIL` | *(empty)* | Sentinel alert recipient; empty → console only |
| `VECTRA_SMTP_HOST` / `VECTRA_SMTP_PORT` | `smtp.gmail.com` / `587` | SMTP server |
| `SMTP_USER` / `SMTP_APP_PASSWORD` | *(empty)* | SMTP credentials |
| `VECTRA_DOCKER_TIMEOUT` | `600` | `docker build`/`run` timeout (seconds) |
| `VECTRA_POLL_INTERVAL_SECONDS` | `600` | Sentinel polling interval |
| `VECTRA_AUTO_INSTALL_DEPS` | `1` | Set `0` to stop patches installing packages locally |
| `VECTRA_VERCEL_PROD` | `0` | Set `1` to deploy Vercel to production instead of preview |

The alert recipient can also be passed per run: `--email you@example.com` on the
CLI, or the `target_email` argument of the MCP tool / dashboard API.

## Architecture

LangGraph workflow with a critic loop and two deploy routes:

```
START → Orchestrator → Critic → Coder → Critic (loop)
      → Docker Gen → Validation → Solomon → Summary → END
      → Vercel Setup → Vercel Deploy ──────→ Summary → END
```

| Node | Responsibility |
|---|---|
| Orchestrator | Turns the deploy prompt into ordered tasks for the repo |
| Critic | Reviews the plan and the coder's output; requests fixes |
| Coder | Edits files in the target repo (patches, deps, env extraction) |
| Docker Gen | Produces the Dockerfile when the repo has none |
| Validation | Builds the image, runs the container, probes the exposed port |
| Solomon | Judges the deployment result and recommends the next move |
| Vercel Setup / Deploy | Prepares and ships frontend projects to Vercel |
| Summary | Writes the final report of what changed and where it runs |

## Dashboard

`vectra/dashboard` is a Vite + React console that talks to
`vectra/dashboard_api.py`:

- `POST /api/run` — start a deployment run
- `GET /api/browse` — browse the filesystem for a target repo
- `GET /api/sentinel/containers` — deployed containers and their status
- `POST /api/sentinel/containers/{id}/start` — restart a stopped container
- `DELETE /api/sentinel/containers/{id}` — remove a container
- `WS /ws` — live run logs

The launcher installs dashboard dependencies if they are missing and starts Vite
with `bun run dev`. To start it by hand:

```bash
cd vectra/dashboard
npm install    # or bun install
bun run dev    # or npm run dev
```

## Sentinel

Sentinel is a standalone daemon that monitors containers deployed by Vectra.

- **Health polling** — checks container status every 10 minutes (configurable).
- **Forensics** — captures exit codes and the last 100 log lines of a crash.
- **AI diagnostics** — a dedicated LangGraph workflow correlates logs with source.
- **Notifications** — sends an HTML report with fix recommendations; falls back to
  the console when SMTP credentials or a recipient are missing.

## Project layout

```
vectra/
  main.py            CLI entry point
  mcp_server.py      FastMCP wrapper around the workflow
  gui.py             launches backend + dashboard dev server
  dashboard_api.py   FastAPI backend for the dashboard
  config.py          all environment-driven settings
  agents/            orchestrator, critic, coder, solomon
  graph/             LangGraph state and workflow wiring
  tools/             docker and vercel tool implementations
  utils/             llm client, file ops, sqlite run history
  dashboard/         React console
sentinel/
  monitor.py         polling daemon
  agents.py          post-mortem workflow
  notifier.py        SMTP reporting
tests/               pytest suite
```

## Tests

```bash
uv run --group dev python -m pytest tests -q
```

The suite covers the coder, critic, and deploy helpers and runs without Ollama,
Docker, or network access.

## Known limitations

- Model output is non-deterministic; the critic loop is what keeps patches honest.
- Validation only probes the port the Dockerfile exposes — it is not a full
  integration test of the deployed app.
- Container state is tracked in a local SQLite file
  (`monitored_containers.sqlite`), so Sentinel is single-machine only.
