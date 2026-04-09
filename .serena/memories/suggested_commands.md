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
ollama pull llama3
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

## Troubleshooting

### Check Ollama Status
```bash
# Check if Ollama is running
curl http://localhost:11434/api/tags

# Test Ollama API
curl http://localhost:11434/api/generate -d "{\"model\":\"llama3\",\"prompt\":\"test\"}"
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
