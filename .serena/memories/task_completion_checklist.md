# BugRewind Task Completion Checklist

## Before Completing a Task

### Code Quality
- [ ] All type hints are correct and complete
- [ ] All functions have appropriate docstrings
- [ ] Code follows project naming conventions
- [ ] Logging is added for important operations
- [ ] Error handling is in place where needed

### Testing
- [ ] Code has been tested manually if applicable
- [ ] Edge cases are considered
- [ ] Docker operations have timeout handling
- [ ] LLM prompts are well-formatted

### Integration
- [ ] New agents are added to the workflow graph
- [ ] State fields are properly defined in `BugRewindState`
- [ ] Reducers are used for accumulated fields (issues, patches)
- [ ] File operations use utility functions from `file_ops.py`

### Documentation
- [ ] README.md is updated if needed
- [ ] New dependencies are added to `pyproject.toml`
- [ ] Code comments explain complex logic

### Dashboard (if applicable)
- [ ] New API endpoints are documented
- [ ] WebSocket updates include all relevant state changes
- [ ] Frontend components handle loading/error states
- [ ] CORS is properly configured for local development

## After Completing a Task

### Verification Steps
1. **Run the main entry point**:
   ```bash
   uv run python -m bugrewind.main /path/to/test/repo --prompt "test"
   ```

2. **Check for errors**:
   - Review console output for exceptions
   - Check logs for warnings or errors

3. **Verify Docker operations** (if applicable):
   - Ensure Dockerfile is generated correctly
   - Test `docker build` succeeds
   - Test `docker run` works

4. **Check output files**:
   - Verify `outputs/summary.md` is generated
   - Review summary content for accuracy

5. **Test Dashboard** (if applicable):
   - Start GUI: `uv run python -m bugrewind.gui`
   - Verify backend is running on http://localhost:8000
   - Verify frontend is running on http://localhost:3000
   - Test WebSocket connection
   - Trigger workflow via API and verify real-time updates

### Common Issues to Check

#### LLM-Related
- Ollama is running: `curl http://localhost:11434/api/tags`
- Model is available: `ollama list`
- API endpoint is correct: `http://localhost:11434/api/generate`

#### Docker-Related
- Docker daemon is running: `docker info`
- Docker CLI is in PATH
- Dockerfile syntax is valid
- Container ports are not conflicting

#### File Operations
- Repository path is valid and accessible
- File permissions are correct
- No files exceed size limits

#### State Management
- State fields are properly initialized
- Reducers work correctly for accumulated fields
- State updates return correct keys

#### Dashboard-Related
- FastAPI server starts without errors
- WebSocket connections are accepted
- CORS allows frontend connections
- Background tasks complete successfully
- Frontend receives WebSocket messages

## When to Ask for Help

If you encounter:
- Persistent LLM API failures
- Docker build/run failures that can't be diagnosed
- State management issues that break the workflow
- Unclear requirements or ambiguous specifications
- WebSocket connection issues
- Frontend build or runtime errors

## Code Review Checklist

### For New Agents
- [ ] Agent has a clear, single responsibility
- [ ] Agent returns a dict with state updates
- [ ] Agent uses `state.get()` with defaults
- [ ] Agent logs its activities
- [ ] Agent is added to the workflow graph
- [ ] Agent has appropriate prompt constants

### For New Tools
- [ ] Tool has proper error handling
- [ ] Tool uses subprocess safely
- [ ] Tool has timeout handling
- [ ] Tool returns structured results
- [ ] Tool is documented

### For State Changes
- [ ] New fields added to `BugRewindState`
- [ ] Field types are appropriate
- [ ] Reducers used for accumulated fields
- [ ] Default values are sensible
- [ ] Field is documented in docstring

### For Dashboard API Changes
- [ ] New endpoints have appropriate HTTP methods
- [ ] Request/response models use Pydantic
- [ ] Async functions used for I/O operations
- [ ] WebSocket broadcasts include all necessary data
- [ ] Error handling returns appropriate status codes
- [ ] CORS is configured correctly

### For Frontend Changes
- [ ] Components follow React best practices
- [ ] State management is appropriate (useState, useEffect, etc.)
- [ ] Error boundaries are in place where needed
- [ ] Loading states are handled
- [ ] WebSocket connections are cleaned up on unmount
- [ ] Icons use lucide-react library
