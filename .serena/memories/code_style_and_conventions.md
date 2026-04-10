# BugRewind Code Style and Conventions

## Naming Conventions
- **Classes**: PascalCase
- **Functions/Variables**: snake_case
- **Constants**: UPPER_SNAKE_CASE
- **LangGraph Nodes**: snake_case with `_node` suffix (e.g. `pm_critic_node`, `dispatcher_node`)
- **Watcher Service**: Files in `watcher/` follow the same conventions as the core.

## Project Structure & Isolation
- **bugrewind/**: Core deployment logic and utilities.
- **watcher/**: Standalone monitoring service. It should NOT depend on `bugrewind.graph` or `bugrewind.agents` to maintain process isolation.
- **bugrewind/utils/db.py**: Shared utility for database access between the two services.

## Monitoring & Forensics
- Use the **Docker Python SDK** (`import docker`) for monitoring and forensics extraction in the watcher.
- Core deployment tasks should still use **subprocess** calls via `tools/docker_tools.py` for simplicity and directness.
- Post-mortem agents in `watcher/agents.py` utilize the standard `call_ollama` utility from `bugrewind.utils.llm`.

## State Management
- **BugRewindState**: Used by the main deployment graph.
- **WatcherState**: Used by the post-mortem diagnostics graph. Defined in `watcher/state.py`.
- Both use `TypedDict` and adhere to type-hinting standards.

## Database Access
- All database operations must go through `bugrewind/utils/db.py`.
- Ensure connection closing in `finally` blocks to avoid locking `monitored_containers.sqlite`.
