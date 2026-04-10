# BugRewind Task Completion Checklist

## Before Completing a Task

### Code Quality
- [ ] All type hints are correct and complete
- [ ] All functions have appropriate docstrings
- [ ] Code follows project naming conventions
- [ ] Logging is added for important operations
- [ ] Error handling is in place where needed
- [ ] Constants are defined at module level with UPPER_SNAKE_CASE
- [ ] Imports are organized (stdlib, third-party, local)

### Testing
- [ ] Code has been tested manually if applicable
- [ ] Edge cases are considered
- [ ] Docker operations have timeout handling
- [ ] LLM prompts are well-formatted
- [ ] Static patterns in Critic agent are tested
- [ ] Build retry logic is tested

### Integration
- [ ] New agents are added to the workflow graph
- [ ] State fields are properly defined in `BugRewindState`
- [ ] Reducers are used for accumulated fields (issues, patches)
- [ ] File operations use utility functions from `file_ops.py`
- [ ] Backup creation is tested before modifications
- [ ] Routing functions are updated for new workflow paths

### Documentation
- [ ] README.md is updated if needed
- [ ] New dependencies are added to `pyproject.toml`
- [ ] Code comments explain complex logic
- [ ] Docstrings include parameter and return descriptions
- [ ] Module-level docstrings explain file purpose

### Dashboard (if applicable)
- [ ] New API endpoints are documented
- [ ] WebSocket updates include all relevant state changes
- [ ] Frontend components handle loading/error states
- [ ] CORS is properly configured for local development
- [ ] Markdown rendering works for summary output

### MCP Server (if applicable)
- [ ] Tool parameters are properly documented
- [ ] Tool returns appropriate format (markdown summary)
- [ ] Logging is set to ERROR level to avoid noise
- [ ] Tool uses `run_workflow()` from graph module

## After Completing a Task

### Verification Steps
1. **Run the interactive launcher**:
   ```bash
   uv run python start.py
   ```
   Test all menu options (GUI, CLI, MCP Server)

2. **Run the main entry point**:
   ```bash
   uv run python -m bugrewind.main /path/to/test/repo --prompt "test"
   ```

3. **Check for errors**:
   - Review console output for exceptions
   - Check logs for warnings or errors
   - Verify backup directory was created

4. **Verify Docker operations** (if applicable):
   - Ensure Dockerfile is generated correctly
   - Test `docker build` succeeds
   - Test `docker run` works
   - Check build retry logic

5. **Check output files**:
   - Verify `outputs/summary.md` is generated
   - Review summary content for accuracy
   - Check `.env` file if secrets were found
   - Verify Dockerfile and .dockerignore

6. **Test Dashboard** (if applicable):
   - Start GUI: `uv run python -m bugrewind.gui`
   - Verify backend is running on http://localhost:8000
   - Verify frontend is running on http://localhost:3000
   - Test WebSocket connection
   - Trigger workflow via API and verify real-time updates
   - Check markdown rendering in dashboard

7. **Test MCP Server** (if applicable):
   - Start MCP server: `uv run python -m bugrewind.mcp_server`
   - Connect from MCP client (Claude Desktop, etc.)
   - Test `orchestrator_tool` function
   - Verify markdown summary is returned

### Common Issues to Check

#### LLM-Related
- Ollama is running: `curl http://localhost:11434/api/tags`
- Model is available: `ollama list`
- API endpoint is correct: `http://localhost:11434/api/generate`
- Prompts are properly formatted with `.format()`
- Response parsing handles errors gracefully

#### Docker-Related
- Docker daemon is running: `docker info`
- Docker CLI is in PATH
- Dockerfile syntax is valid
- Container ports are not conflicting
- Build retry logic respects MAX_BUILD_RETRIES
- Timeout handling for long-running operations

#### File Operations
- Repository path is valid and accessible
- File permissions are correct
- No files exceed size limits
- Backup directory is created before modifications
- Skipped directories are properly ignored (.venv, node_modules, etc.)

#### State Management
- State fields are properly initialized
- Reducers work correctly for accumulated fields
- State updates return correct keys
- `state.get()` is used with defaults for optional fields
- Build attempts counter is incremented correctly

#### Dashboard-Related
- FastAPI server starts without errors
- WebSocket connections are accepted
- CORS allows frontend connections
- Background tasks complete successfully
- Frontend receives WebSocket messages
- Markdown rendering works with react-markdown
- Icons display correctly with lucide-react

#### MCP Server-Related
- Server starts without errors
- Tool is properly registered with FastMCP
- Logging is silenced (ERROR level)
- Tool returns markdown summary string
- stdio communication works with MCP clients

#### GUI Launcher-Related
- Backend process starts successfully
- Frontend process starts successfully
- Processes terminate gracefully on KeyboardInterrupt
- Node modules are installed if missing
- Process health is monitored

## When to Ask for Help

If you encounter:
- Persistent LLM API failures
- Docker build/run failures that can't be diagnosed
- State management issues that break the workflow
- Unclear requirements or ambiguous specifications
- WebSocket connection issues
- Frontend build or runtime errors
- MCP server communication problems
- Static pattern matching issues in Critic agent
- Backup creation failures

## Code Review Checklist

### For New Agents
- [ ] Agent has a clear, single responsibility
- [ ] Agent returns a dict with state updates
- [ ] Agent uses `state.get()` with defaults
- [ ] Agent logs its activities
- [ ] Agent is added to the workflow graph
- [ ] Agent has appropriate prompt constants
- [ ] Agent handles errors gracefully
- [ ] Agent is documented in project_overview memory

### For New Tools
- [ ] Tool has proper error handling
- [ ] Tool uses subprocess safely
- [ ] Tool has timeout handling
- [ ] Tool returns structured results
- [ ] Tool is documented
- [ ] Tool is imported and used correctly

### For State Changes
- [ ] New fields added to `BugRewindState`
- [ ] Field types are appropriate
- [ ] Reducers used for accumulated fields
- [ ] Default values are sensible
- [ ] Field is documented in docstring
- [ ] All agents that need the field are updated

### For Dashboard API Changes
- [ ] New endpoints have appropriate HTTP methods
- [ ] Request/response models use Pydantic
- [ ] Async functions used for I/O operations
- [ ] WebSocket broadcasts include all necessary data
- [ ] Error handling returns appropriate status codes
- [ ] CORS is configured correctly
- [ ] ConnectionManager is updated if needed

### For Frontend Changes
- [ ] Components follow React best practices
- [ ] State management is appropriate (useState, useEffect, etc.)
- [ ] Error boundaries are in place where needed
- [ ] Loading states are handled
- [ ] WebSocket connections are cleaned up on unmount
- [ ] Icons use lucide-react library
- [ ] Markdown rendering uses react-markdown and remark-gfm

### For MCP Server Changes
- [ ] Tool is decorated with `@mcp.tool`
- [ ] Tool parameters are properly typed
- [ ] Tool docstring is comprehensive
- [ ] Tool returns markdown summary
- [ ] Tool uses `run_workflow()` from graph module
- [ ] Logging is set to ERROR level

### For CLI Changes
- [ ] Arguments are added to argparse
- [ ] Default values are sensible
- [ ] Help text is clear
- [ ] Flags follow conventions (--prompt, --max-iter, --verbose)
- [ ] Arguments are passed to workflow correctly

### For GUI Launcher Changes
- [ ] Process startup is handled correctly
- [ ] Process termination is graceful
- [ ] Error messages are clear
- [ ] Dependencies are checked before starting
- [ ] KeyboardInterrupt is handled

## Security Considerations

### When Working with Secrets
- [ ] Never log secrets or sensitive data
- [ ] Use environment variables for secrets
- [ ] Create `.env` file for hardcoded secrets
- [ ] Update code to read from environment variables
- [ ] Add `.env` to `.gitignore`

### When Working with Subprocess
- [ ] Sanitize shell commands
- [ ] Use subprocess with proper arguments
- [ ] Avoid shell=True when possible
- [ ] Validate user input before execution

### When Working with Docker
- [ ] Don't expose unnecessary ports
- [ ] Use non-root users in containers
- [ ] Scan images for vulnerabilities
- [ ] Use minimal base images

## Performance Considerations

### LLM Calls
- [ ] Minimize number of LLM calls
- [ ] Use static patterns for common issues
- [ ] Cache results when appropriate
- [ ] Set reasonable timeouts

### File Operations
- [ ] Skip unnecessary directories
- [ ] Use efficient file reading
- [ ] Don't read binary files
- [ ] Limit file sizes

### Docker Operations
- [ ] Use build cache effectively
- [ ] Clean up old images
- [ ] Set appropriate timeouts
- [ ] Monitor resource usage

## Testing Checklist

### Unit Testing (if applicable)
- [ ] Test individual functions
- [ ] Test edge cases
- [ ] Test error conditions
- [ ] Mock external dependencies

### Integration Testing
- [ ] Test agent interactions
- [ ] Test state transitions
- [ ] Test workflow routing
- [ ] Test error recovery

### End-to-End Testing
- [ ] Test complete workflow
- [ ] Test with real repositories
- [ ] Test Docker build and run
- [ ] Test dashboard functionality
- [ ] Test MCP server integration

## Deployment Checklist

### Before Deploying
- [ ] All tests pass
- [ ] Documentation is updated
- [ ] Dependencies are pinned
- [ ] Security scan is clean
- [ ] Performance is acceptable

### After Deploying
- [ ] Monitor logs for errors
- [ ] Check resource usage
- [ ] Verify functionality
- [ ] Gather user feedback
