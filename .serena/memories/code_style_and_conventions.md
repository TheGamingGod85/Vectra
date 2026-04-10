# BugRewind Code Style and Conventions

## Naming Conventions
- **Classes**: PascalCase (e.g., `BugRewindState`, `ConnectionManager`)
- **Functions/Variables**: snake_case (e.g., `orchestrator_node`, `repo_path`)
- **Constants**: UPPER_SNAKE_CASE (e.g., `ORCHESTRATOR_PROMPT`, `OLLAMA_URL`, `STATIC_PATTERNS`, `MAX_BUILD_RETRIES`)
- **React Components**: PascalCase (e.g., `App.jsx`, `Dashboard.jsx`)
- **API Models**: PascalCase (e.g., `runRequest`)
- **LangGraph Nodes**: snake_case with `_node` suffix (e.g., `orchestrator_node`, `critic_node`)

## Type Hints
- All functions use type hints
- Uses `TypedDict` for state management
- Uses `Annotated` types with reducers (e.g., `Annotated[list[dict], operator.add]`)
- Return types explicitly declared (e.g., `-> dict`, `-> None`)
- FastAPI uses Pydantic models for request/response validation
- Uses `from __future__ import annotations` for forward references

## Docstrings
- All classes and functions have docstrings
- Docstrings describe purpose, parameters, and return values
- Module-level docstrings explain the file's purpose
- Example format:
```python
def orchestrator_node(state: BugRewindState) -> dict:
    """LangGraph node: Orchestrator.

    Reads the repo, creates a backup, builds the codebase context, calls the LLM to produce an
    execution plan, and populates the shared state.
    """
```

## Logging
- Uses Python's `logging` module
- Structured log messages with context
- Logger instances defined at module level: `logger = logging.getLogger(__name__)`
- Log levels: DEBUG, INFO, WARNING, ERROR
- Log format includes timestamp, name, level, and message
- MCP server uses ERROR level logging to stderr to avoid noise

## Code Organization
- Each agent is in its own file under `agents/`
- Utility functions in `utils/`
- Tools in `tools/`
- Graph definition in `graph/`
- Entry points at root level (`main.py`, `mcp_server.py`, `dashboard_api.py`, `gui.py`)
- Dashboard frontend in `dashboard/` directory
- Interactive launcher at root level (`start.py`)

## Constants
- Configuration constants defined at module level
- Examples: `OLLAMA_URL`, `DEFAULT_MODEL`, `REQUEST_TIMEOUT`, `DOCKER_TIMEOUT`, `MAX_BUILD_RETRIES`
- Prompts stored as constants (e.g., `ORCHESTRATOR_PROMPT`, `CRITIC_PROMPT`, `CODER_FIX_PROMPT`)
- Static patterns stored as tuples in lists (e.g., `STATIC_PATTERNS`)

## Error Handling
- Uses try-except blocks for subprocess operations
- Returns error messages in state fields (e.g., `docker_status: "build_failed"`)
- Logs errors appropriately
- WebSocket connections handle disconnects gracefully
- Process termination in GUI launcher uses `terminate()` with timeout fallback to `kill()`

## File Operations
- Uses `pathlib.Path` for path operations
- File reading/writing through utility functions in `file_ops.py`
- Skips certain directories (`.venv`, `node_modules`, `.git`, `__pycache__`, etc.)
- Creates backup of original codebase before modifications
- Uses `apply_patch()` function for targeted code changes

## LLM Integration
- All LLM calls go through `call_ollama()` or `call_ollama_json()` in `utils/llm.py`
- Prompts are formatted with `.format()` method
- Response parsing handled by dedicated functions (e.g., `_parse_issues`, `_parse_patches`)
- Critic agent uses both static pattern scanning and LLM analysis

## Docker Operations
- Docker commands executed via `subprocess` in `tools/docker_tools.py`
- Timeout handling for long-running operations
- Logs captured and stored in state
- Build retry mechanism with `MAX_BUILD_RETRIES` constant

## State Updates
- LangGraph nodes return dictionaries with state updates
- Use `state.get()` with defaults for optional fields
- Accumulated fields use `operator.add` reducer
- State fields are documented in `BugRewindState` docstring

## FastAPI Conventions
- Use `async` for endpoints that perform I/O
- Use Pydantic models for request/response validation
- Enable CORS for local development
- WebSocket connections managed via `ConnectionManager` class
- Background tasks for long-running operations
- Use `asyncio.create_task()` for background workflow execution

## React/Vite Conventions
- Functional components with hooks
- Use `lucide-react` for icons
- CSS modules or global CSS in `index.css`
- WebSocket connections for real-time updates
- Component files in `src/` directory
- Use `react-markdown` and `remark-gfm` for markdown rendering

## Dashboard API Patterns
- WebSocket endpoint at `/ws` for real-time updates
- POST endpoint at `/api/run` to trigger workflow
- Health check at `/health`
- Use `asyncio.create_task()` for background workflow execution
- Broadcast state updates to all connected WebSocket clients
- ConnectionManager class manages active WebSocket connections

## GUI Launcher Conventions
- Uses `subprocess.Popen` to start backend and frontend
- Handles `KeyboardInterrupt` for graceful shutdown
- Checks for `node_modules` and runs `npm install` if needed
- Monitors process health and reports failures
- Uses `_terminate_process()` helper for graceful process termination

## Interactive Launcher Conventions
- Menu-driven interface with numbered options
- Uses `input()` for user interaction
- Subprocess execution for all modes
- Graceful exit on invalid choices
- Clear header and menu formatting

## Agent-Specific Conventions

### Orchestrator Agent
- Creates backup before any modifications
- Builds codebase context from repository
- Produces structured execution plan
- Uses `create_backup()` utility function

### Critic Agent
- Uses static regex patterns for common vulnerabilities
- Falls back to LLM analysis for complex issues
- Returns structured issue objects with severity, description, file, and code snippet
- Severity levels: critical, high, medium, low

### Coder Agent
- NEVER deletes functionality - only replaces insecure code
- Creates `.env` file for hardcoded secrets
- Generates Dockerfile and .dockerignore when missing
- Detects new imports and installs missing dependencies
- Uses `apply_patch()` for targeted changes

### Solomon Agent
- Only agent allowed to run shell commands
- Executes Docker builds and container starts
- Feeds error logs back to state for Critic re-analysis
- Tracks build attempts for retry logic

## MCP Server Conventions
- Uses FastMCP library
- Exposes single `orchestrator_tool` function
- Logging set to ERROR level to stderr
- Tool returns markdown summary string
- Uses `run_workflow()` from graph module

## CLI Conventions
- Uses `argparse` for command-line argument parsing
- Supports `--prompt` for deployment instructions
- Supports `--max-iter` for iteration limit
- Supports `--verbose` / `-v` for DEBUG logging
- Default prompt: "Deploy this project securely via Docker."
- Default max iterations: 3

## Import Organization
- Standard library imports first
- Third-party imports second
- Local imports third
- Each section separated by blank line
- Use `from __future__ import annotations` at top of files

## String Formatting
- Use `.format()` for string formatting (not f-strings for prompts)
- Use f-strings for simple variable interpolation in logging
- Use triple-quoted strings for multi-line prompts

## Comment Style
- Use `# ── Section ──` for major section dividers
- Use inline comments for complex logic
- Keep comments concise and relevant
- Document non-obvious code patterns
