# Vectra Code Style and Conventions

## Naming Conventions
- **Classes**: PascalCase
- **Functions/Variables**: snake_case
- **Constants**: UPPER_SNAKE_CASE
- **LangGraph Nodes**: snake_case with `_node` suffix (e.g. `pm_critic_node`, `dispatcher_node`)
- **Watcher Service**: Files in `sentinel/` follow the same conventions as the core.

## Project Structure & Isolation
- **vectra/**: Core deployment logic and utilities.
- **sentinel/**: Standalone monitoring service. It should NOT depend on `vectra.graph` or `vectra.agents` to maintain process isolation.
- **vectra/utils/db.py**: Shared utility for database access between the two services.

## Monitoring & Forensics
- Use the **Docker Python SDK** (`import docker`) for monitoring and forensics extraction in the sentinel.
- Core deployment tasks should still use **subprocess** calls via `tools/docker_tools.py` for simplicity and directness.
- Post-mortem agents in `sentinel/agents.py` utilize the standard `call_ollama` utility from `vectra.utils.llm`.

## State Management
- **VectraState**: Used by the main deployment graph.
- **WatcherState**: Used by the post-mortem diagnostics graph. Defined in `sentinel/state.py`.
- Both use `TypedDict` and adhere to type-hinting standards.

## Database Access
- All database operations must go through `vectra/utils/db.py`.
- Ensure connection closing in `finally` blocks to avoid locking `monitored_containers.sqlite`.

## Prompt Files
- **System Prompts**: Located in `.prompts/` directory
  - `PROMPT.md`: Main system prompt for the Vectra AI agent
  - `REWINDPROMPT.md`: Specification for Sentinel implementation
- **Usage**: These prompts guide AI development and should be referenced when implementing new features
- **Updates**: When modifying agent behavior, check if corresponding prompt updates are needed
