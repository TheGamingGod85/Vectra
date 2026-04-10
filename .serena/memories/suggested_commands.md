# BugRewind Suggested Commands

## Development Commands

### Install Dependencies
```bash
uv sync
```

### Interactive Launcher (Recommended)
```bash
uv run python start.py
```
This provides a menu-driven interface to choose between:
1. GUI Dashboard (Interactive Web UI)
2. CLI Automation (Headless terminal scan)
3. MCP Server (Protocol for AI Assistants)
4. Exit

### Run Against Target Repository (CLI)
```bash
uv run python -m bugrewind.main /path/to/repo --prompt "Deploy securely"
```

### Run with Verbose Logging
```bash
uv run python -m bugrewind.main /path/to/repo --prompt "Deploy securely" --verbose
```

### Run with Custom Iteration Limit
```bash
uv run python -m bugrewind.main /path/to/repo --prompt "Deploy securely" --max-iter 5
```

### Run as MCP Server
```bash
uv run python -m bugrewind.mcp_server
```

### Launch Dashboard (GUI)
```bash
uv run python -m bugrewind.gui
```
This starts both the FastAPI backend (port 8000) and Vite frontend (port 3000).

### Start Dashboard Backend Only
```bash
uv run uvicorn bugrewind.dashboard_api:app --reload
```

### Start Dashboard Frontend Only
```bash
cd bugrewind/dashboard
npm install  # First time only
npm run dev
```

### Using Installed Scripts
```bash
# After uv sync, scripts are available:
bugrewind /path/to/repo --prompt "Deploy securely"
bugrewind-mcp
```

## Prerequisites Setup

### Install Ollama
```bash
# Download from https://ollama.ai
# Pull required model:
ollama pull kimi-k2.5:cloud
# or
ollama pull codellama
```

### Install Docker
```bash
# Install Docker Desktop for Windows
# Ensure Docker CLI is available in PATH
docker --version
```

### Install uv (if not already installed)
```bash
# Using pip
pip install uv

# Or using the official installer
# See https://github.com/astral-sh/uv
```

### Install Node.js (for Dashboard)
```bash
# Download from https://nodejs.org
# Verify installation:
node --version
npm --version
```

## Windows Utility Commands

### File System Operations
```bash
# List directory contents
dir

# List recursively
dir /s

# Display file contents
type filename.txt

# Search in files
findstr "pattern" filename.txt

# Copy files
copy source.txt dest.txt

# Move files
move source.txt dest.txt

# Delete files
del filename.txt

# Create directory
mkdir dirname

# Remove directory
rmdir dirname

# Remove directory recursively
rmdir /s /q dirname
```

### Git Commands
```bash
# Initialize repository
git init

# Clone repository
git clone <url>

# Check status
git status

# Add files
git add .

# Commit changes
git commit -m "message"

# Push changes
git push

# Pull changes
git pull

# View log
git log
```

## Testing and Validation

### Test Docker Build
```bash
docker build -t test-image .
```

### Test Docker Run
```bash
docker run test-image
```

### Stop Running Containers
```bash
docker ps
docker stop <container-id>
```

### View Docker Logs
```bash
docker logs <container-id>
```

### Test Dashboard API
```bash
# Health check
curl http://localhost:8000/health

# Trigger workflow (requires JSON payload)
curl -X POST http://localhost:8000/api/run -H "Content-Type: application/json" -d "{\"repo_path\":\"/path/to/repo\",\"deploy_prompt\":\"Deploy securely\"}"
```

## Troubleshooting

### Check Ollama Status
```bash
# Check if Ollama is running
curl http://localhost:11434/api/tags

# Test Ollama API
curl http://localhost:11434/api/generate -d "{\"model\":\"kimi-k2.5:cloud\",\"prompt\":\"test\"}"
```

### Check Python Environment
```bash
# Check Python version
python --version

# Check installed packages
uv pip list

# Run Python REPL
uv run python
```

### Check Docker Status
```bash
# Check Docker daemon
docker info

# List images
docker images

# List containers
docker ps -a
```

### Dashboard Issues
```bash
# Check if backend is running
curl http://localhost:8000/health

# Check if frontend is running
curl http://localhost:3000

# Reinstall frontend dependencies
cd bugrewind/dashboard
del package-lock.json
rmdir /s /q node_modules
npm install
```

### MCP Server Issues
```bash
# Test MCP server connection
# The MCP server communicates via stdio, so testing requires an MCP client
# Common clients: Claude Desktop, Cursor, etc.

# Check if server starts without errors
uv run python -m bugrewind.mcp_server
```

## Development Workflow

### Typical Development Cycle
```bash
# 1. Make code changes
# 2. Run tests (if applicable)
# 3. Test with a sample repository
uv run python -m bugrewind.main /path/to/test/repo --prompt "test"

# 4. Test dashboard
uv run python -m bugrewind.gui

# 5. Test MCP server
uv run python -m bugrewind.mcp_server
```

### Debugging with Verbose Logging
```bash
# Enable DEBUG level logging
uv run python -m bugrewind.main /path/to/repo --prompt "test" --verbose
```

### Testing Specific Agents
```bash
# You can test individual agents by modifying the workflow
# or by creating test scripts that call specific nodes directly
```

## Project-Specific Commands

### Check Backup Directory
```bash
# The Orchestrator creates a backup before modifications
# Check for backup directory in the target repository
dir /a /b | findstr "backup"
```

### View Generated Summary
```bash
# After workflow completion, view the summary
type outputs\summary.md
```

### Check Generated Docker Files
```bash
# View generated Dockerfile
type Dockerfile

# View generated .dockerignore
type .dockerignore

# View generated .env file (if secrets were found)
type .env
```

## Performance Optimization

### Clean Docker Resources
```bash
# Remove unused images
docker image prune

# Remove all unused resources
docker system prune -a

# Remove stopped containers
docker container prune
```

### Clean Python Cache
```bash
# Remove __pycache__ directories
for /d /r . %d in (__pycache__) do @if exist "%d" rd /s /q "%d"

# Remove .pyc files
del /s /q *.pyc
```

## Environment Variables

### Setting Environment Variables (Windows CMD)
```bash
# Set Ollama URL (if not default)
set OLLAMA_URL=http://localhost:11434

# Set log level
set LOG_LEVEL=DEBUG
```

### Setting Environment Variables (Windows PowerShell)
```powershell
# Set Ollama URL (if not default)
$env:OLLAMA_URL="http://localhost:11434"

# Set log level
$env:LOG_LEVEL="DEBUG"
```

## Quick Reference

### Entry Points Summary
| Command | Purpose |
|---------|---------|
| `uv run python start.py` | Interactive menu launcher |
| `uv run python -m bugrewind.main` | CLI automation |
| `uv run python -m bugrewind.mcp_server` | MCP server |
| `uv run python -m bugrewind.gui` | GUI dashboard |
| `bugrewind` | Installed CLI script |
| `bugrewind-mcp` | Installed MCP script |

### Common Flags
| Flag | Description |
|------|-------------|
| `--prompt` | Deployment instructions |
| `--max-iter` | Maximum Critic-Coder iterations |
| `--verbose`, `-v` | Enable DEBUG logging |

### Default Values
- Default prompt: "Deploy this project securely via Docker."
- Default max iterations: 3
- Default log level: INFO
- Backend port: 8000
- Frontend port: 3000
- Ollama URL: http://localhost:11434
