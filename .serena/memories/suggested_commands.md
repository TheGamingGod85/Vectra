# BugRewind Suggested Commands

## BugRewind (Deployment Service)

### Install Dependencies
```bash
uv sync
```

### Interactive Launcher
```bash
uv run python start.py
```

### CLI Deployment
```bash
uv run python -m bugrewind.main /path/to/repo --prompt "Deploy securely"
```

## RewindWatcher (Monitoring Service)

### Start Monitoring Daemon
```bash
uv run python watcher/monitor.py
```

### SMTP Configuration (Required for Email Alerts)
```powershell
# Windows PowerShell
$env:SMTP_USER="your-email@gmail.com"
$env:SMTP_APP_PASSWORD="your-app-password"
```

```bash
# Windows CMD
set SMTP_USER=your-email@gmail.com
set SMTP_APP_PASSWORD=your-app-password
```

## Database Operations

### Query Monitored Containers
```bash
sqlite3 monitored_containers.sqlite "SELECT * FROM containers;"
```

## Docker Management

### List Active Monitored Containers
```bash
docker ps --filter "name=bugrewind-container"
```

### View Watcher Logs
Watcher logs are printed directly to the console during `python watcher/monitor.py` execution.

### Clean Docker Environment
```bash
docker system prune -f
```
