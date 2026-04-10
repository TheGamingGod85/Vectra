# BugRewind Suggested Commands

## Development Commands

### Install Dependencies
```bash
uv sync
```

### Run Against Target Repository
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
