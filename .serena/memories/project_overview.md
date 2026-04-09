# BugRewind Project Overview

## Purpose
BugRewind is an AI-powered secure deployment system using multi-agent orchestration. It analyzes codebases, detects vulnerabilities, iteratively fixes issues, generates deployment configs, validates via Docker, and deploys locally.

## Tech Stack
- **Language**: Python 3.11+
- **Package Manager**: uv
- **LLM**: Ollama API (llama3 or codellama)
- **Agent Framework**: LangGraph
- **MCP Server**: FastMCP
- **Docker**: Docker CLI (subprocess)
- **Dependencies**: langgraph, langchain-core, langchain-ollama, fastmcp, httpx, pydantic

## Architecture
LangGraph-based multi-agent workflow with the following agents:

1. **Orchestrator Agent**: Entry point that understands repo + user intent, creates execution plan
2. **Critic Agent**: Security + quality reviewer that detects vulnerabilities (secrets, unsafe shell usage, dependency risks, missing Dockerfile)
3. **Coder Agent**: Applies fixes based on critic findings (does NOT rewrite entire repo)
4. **Solomon Agent**: Execution agent that runs shell commands and executes Docker

## Workflow Graph
```
START → Orchestrator → Critic → Coder → Critic (loop)
      → Docker Gen → Validation → Solomon → Summary → END
```

The Critic-Coder loop continues until iteration limit or no issues remain.

## State Management
Uses `BugRewindState` TypedDict with fields:
- repo_path, deploy_prompt, codebase, file_manifest
- plan, issues, patches, iteration, max_iterations
- dockerfile, dockerignore, docker_build_log, docker_run_log, docker_status
- logs, summary

Issues and patches use `operator.add` reducer for accumulation.

## Project Structure
```
bugrewind/
├── main.py              # CLI entry point
├── mcp_server.py        # MCP server entry point
├── graph/
│   ├── state.py         # BugRewindState TypedDict
│   └── workflow.py      # LangGraph workflow definition
├── agents/
│   ├── orchestrator.py  # Entry point agent
│   ├── critic.py        # Security/quality reviewer
│   ├── coder.py         # Applies fixes
│   └── solomon.py       # Execution agent (Docker)
├── tools/
│   └── docker_tools.py  # Docker CLI wrappers
├── utils/
│   ├── llm.py           # Ollama API wrapper
│   └── file_ops.py      # File operations
└── outputs/
    └── summary.md       # Generated summary
```

## Key Design Patterns
- Each agent is a distinct LangGraph node
- State travels through the entire workflow
- Clear separation of responsibilities
- Iterative improvement loop between Critic and Coder
- Docker validation before final deployment
