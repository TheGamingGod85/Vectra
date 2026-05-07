# Comprehensive Build Specification: Sentinel

**Objective**: 
Create **Sentinel**, a standalone background monitoring daemon and post-mortem AI diagnostics engine. This tool runs entirely independently of the existing **Vectra** dashboard, monitoring containers that Vectra has successfully deployed. Upon detecting a container crash, Sentinel triggers a localized LangGraph workflow to diagnose the root cause, map it to the original source code, and dispatch targeted email notifications.

This document serves as a strict technical specification for an AI agent to implement Sentinel and modify Vectra accordingly.

---

## 1. Vectra System Modifications (The Handoff)

We must establish a decoupled handoff mechanism so Vectra can tell Sentinel what to monitor without blocking its own UI or LangGraph execution.

### 1.1 Database Initialization
Create a new file `vectra/utils/db.py` to initialize a SQLite database `monitored_containers.sqlite` in the project root. 
**Schema Requirement**:
```sql
CREATE TABLE IF NOT EXISTS containers (
    id TEXT PRIMARY KEY,
    container_id TEXT NOT NULL,
    repository_path TEXT NOT NULL,
    target_email TEXT NOT NULL,
    status TEXT DEFAULT 'monitoring',
    deployed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### 1.2 Deployment Hook in `solomon.py`
In `vectra/agents/solomon.py`, locate the `solomon_node` or `validation_node` where Docker `run` is executed successfully. Upon a successful run:
1. Generate a UUID for the record.
2. Insert a row into the database linking the `container_id` returned by Docker to the `state["repo_path"]`.
3. Provide a default fallback email (e.g., `marcus32holloway@gmail.com`) if a real one is not present in the state.

---

## 2. Sentinel Architecture (`watcher/`)

Create a new directory named `watcher` at the project root. This service must run in its own Python process.

### 2.1 The Polling Loop (`watcher/monitor.py`)
Implement the core monitoring loop using `apscheduler` (BackgroundScheduler) or a standard `asyncio` while-loop. 
- **Frequency**: Run the check every 10 minutes.
- **Action**: Query the database for all records where `status = 'monitoring'`.
- **Health Check**: Use the `docker` python SDK (`import docker; client = docker.from_env()`). Iterate through the queried container IDs and retrieve their status (`container.status`).
- **Trigger**: If `status == 'exited'`, update the database status to `analyzing` and trigger the **Forensics Workflow**. If `container.status` is clean, do nothing.

### 2.2 Forensics Data Extraction
When an `exited` container is found, execute a forensics script to collect the state:
- Fetch `container.attrs['State']['ExitCode']`.
- Fetch `container.attrs['State']['OOMKilled']`.
- Extract the last 100 lines of logs using `container.logs(tail=100)`.
- Pass these data points, along with the `repository_path` from the database, into the LangGraph state.

---

## 3. Post-Mortem AI Workflow (LangGraph)

Create `watcher/graph.py` and `watcher/agents.py`. This workflow operates entirely independently of Vectra's main deployment graph.

### 3.1 Watcher State (`WatcherState` TypedDict)
```python
class WatcherState(TypedDict):
    container_id: str
    repo_path: str
    exit_code: int
    is_oom_killed: bool
    container_logs: str
    source_code_context: str # Manifest or snippet of codebase read from repo_path
    root_cause_category: str # 'infrastructure' | 'source_code' | 'unknown'
    diagnostic_report: str
    fix_recommendation: str
    target_email: str
```

### 3.2 Post-Mortem (PM) Critic Node
- **Role**: Root Cause Analyst.
- **Input**: `container_logs`, `exit_code`, and codebase context pulled from `repo_path`.
- **System Prompt Guidelines**: 
  "You are an expert site reliability engineer. Analyze these Docker logs and the provided source code. Correlate stack traces in the logs to the exact files and line numbers in the source code. Categorize the failure as 'infrastructure' (e.g., missing env vars, DB unreachable, OOM killed) or 'source_code' (e.g., unhandled exceptions, logical errors, syntax bugs). Produce a diagnostic report."
- **Output**: Updates `root_cause_category` and `diagnostic_report`.

### 3.3 Post-Mortem (PM) Coder Node
- **Role**: Solution Architect.
- **Input**: The `diagnostic_report` and `source_code_context`.
- **System Prompt Guidelines**:
  "You are a Senior Software Engineer. Review the diagnostic report of this crashed service. Formulate an actionable, step-by-step fix recommendation. If the issue is in the source code, provide the exact code changes needed. Do not execute the changes; just format them beautifully for an email report."
- **Output**: Updates `fix_recommendation`.

---

## 4. Intelligent Notification Dispatch (`watcher/notifier.py`)

Create a terminal/mock mailer that routes the workflow's conclusions to the appropriate parties based on the `root_cause_category`.

### 4.1 Dispatch Routing Logic
Implement a `dispatcher_node` at the end of the LangGraph workflow:

For both cases below, the **Recipient** is the `target_email`:

* **IF `root_cause_category == 'infrastructure'`:**
  - **Subject**: [Sentinel Alert] Container {id} crashed due to Configuration Error
  - **Body**: Include the `diagnostic_report`. Inform the user that infrastructural configuration (like environment variables or linked services) needs to be corrected in their local environment/prompt.

* **IF `root_cause_category == 'source_code'`:**
  - **Subject**: [Sentinel Alert] Code Exception in Container {id}
  - **Body**: Include the full log trace, `diagnostic_report`, and the `fix_recommendation` produced by the PM Coder. Point out the optimized source reference (file path and line number) derived from the `repo_path` context so they can easily apply the fix to the source.

* **Action Output**: Implement real email dispatch using `smtplib`. Configure it to use Gmail SMTP (`smtp.gmail.com:587`). Read the sender credentials from environment variables (`SMTP_USER` and `SMTP_APP_PASSWORD`). Send actual emails to the designated `target_email` address.

---

## 5. Execution & Tooling Requirements
- **LLM Consistency**: The watcher must utilize the exact same Ollama / LLM abstraction layer found in `vectra.utils.llm` to ensure model consistency.
- **Isolation**: Running `python watcher/monitor.py` should start a foreground blocking process that handles the scheduling and AI execution without requiring `uvicorn` or any web dependencies. 
- **Graceful Failure**: If the LLM is down or times out during Post-Mortem Analysis, log the timeout to the console but do not crash the watcher loop. Try the analysis again on the next polling cycle.
