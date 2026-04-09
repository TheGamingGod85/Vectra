# BugRewind Code Style and Conventions

## Naming Conventions
- **Classes**: PascalCase (e.g., `BugRewindState`)
- **Functions/Variables**: snake_case (e.g., `orchestrator_node`, `repo_path`)
- **Constants**: UPPER_SNAKE_CASE (e.g., `ORCHESTRATOR_PROMPT`, `OLLAMA_URL`)

## Type Hints
- All functions use type hints
- Uses `TypedDict` for state management
- Uses `Annotated` types with reducers (e.g., `Annotated[list[dict], operator.add]`)
- Return types explicitly declared (e.g., `-> dict`, `-> None`)

## Docstrings
- All classes and functions have docstrings
- Docstrings describe purpose, parameters, and return values
- Example format:
```python
def orchestrator_node(state: BugRewindState) -> dict:
    """LangGraph node: Orchestrator.

    Reads the repo, builds the codebase context, calls the LLM to produce an
    execution plan, and populates the shared state.
    """
```

## Logging
- Uses Python's `logging` module
- Structured log messages with context
- Logger instances defined at module level: `logger = logging.getLogger(__name__)`
- Log levels: DEBUG, INFO, WARNING, ERROR
- Log format includes timestamp, name, level, and message

## Code Organization
- Each agent is in its own file under `agents/`
- Utility functions in `utils/`
- Tools in `tools/`
- Graph definition in `graph/`
- Entry points at root level

## Constants
- Configuration constants defined at module level
- Examples: `OLLAMA_URL`, `DEFAULT_MODEL`, `REQUEST_TIMEOUT`, `DOCKER_TIMEOUT`
- Prompts stored as constants (e.g., `ORCHESTRATOR_PROMPT`, `CRITIC_PROMPT`)

## Error Handling
- Uses try-except blocks for subprocess operations
- Returns error messages in state fields (e.g., `docker_status: "build_failed"`)
- Logs errors appropriately

## File Operations
- Uses `pathlib.Path` for path operations
- File reading/writing through utility functions in `file_ops.py`
- Skips certain directories (`.venv`, `node_modules`, etc.)

## LLM Integration
- All LLM calls go through `call_ollama()` or `call_ollama_json()` in `utils/llm.py`
- Prompts are formatted with `.format()` method
- Response parsing handled by dedicated functions (e.g., `_parse_issues`, `_parse_patches`)

## Docker Operations
- Docker commands executed via `subprocess` in `tools/docker_tools.py`
- Timeout handling for long-running operations
- Logs captured and stored in state

## State Updates
- LangGraph nodes return dictionaries with state updates
- Use `state.get()` with defaults for optional fields
- Accumulated fields use `operator.add` reducer
