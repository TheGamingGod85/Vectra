"""
BugRewind Dashboard API.

FastAPI server that exposes the LangGraph workflow over WebSockets 
for real-time visualization and management.
"""

import asyncio
import logging
import os
from typing import Dict, Any

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from bugrewind.graph.workflow import build_workflow, _detect_deploy_target
from bugrewind.graph.state import BugRewindState

# ── Setup ──────────────────────────────────────────────────────────────────

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="BugRewind Dashboard API")

# Enable CORS for local dev
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Models ──────────────────────────────────────────────────────────────────

class runRequest(BaseModel):
    repo_path: str
    deploy_prompt: str = "Deploy this project securely via Docker."
    max_iterations: int = 3
    deploy_target: str | None = None

# ── State ──────────────────────────────────────────────────────────────────

# Active websocket connections
class ConnectionManager:
    def __init__(self):
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def broadcast(self, message: dict):
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception:
                pass

manager = ConnectionManager()

# ── Endpoints ───────────────────────────────────────────────────────────────

@app.get("/health")
async def health():
    return {"status": "ok"}

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            # Just keep connection alive, we primarily broadcast
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)

@app.get("/api/browse")
async def browse_folder():
    import subprocess
    import sys
    
    # Securely use PowerShell on Windows to invoke the native Folder Browser Dialog
    if os.name == 'nt':
        ps_script = (
            "Add-Type -AssemblyName System.windows.forms; "
            "$f = New-Object System.Windows.Forms.FolderBrowserDialog; "
            "$f.Description = 'Select Repository Folder'; "
            "$f.ShowNewFolderButton = $true; "
            "if ($f.ShowDialog() -eq [System.Windows.Forms.DialogResult]::OK) { Write-Output $f.SelectedPath }"
        )
        cmd = ["powershell", "-NoProfile", "-Command", ps_script]
        creationflags = getattr(subprocess, 'CREATE_NO_WINDOW', 0x08000000)
    else:
        # Fallback to tkinter for linux/mac if used
        py_code = (
            "import tkinter as tk; from tkinter import filedialog; "
            "root = tk.Tk(); root.withdraw(); root.attributes('-topmost', True); "
            "print(filedialog.askdirectory(parent=root, title='Select Repository Folder')); "
            "root.destroy()"
        )
        cmd = [sys.executable, "-c", py_code]
        creationflags = 0

    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            creationflags=creationflags
        )
        stdout, _ = await proc.communicate()
        folder_path = stdout.decode('utf-8').strip()
    except Exception as e:
        logger.error("Failed to open dialog: %s", e)
        folder_path = ""
        
    return {"path": folder_path}

@app.post("/api/run")
async def trigger_run(req: runRequest):
    """Start an async workflow run and stream events to WebSocket."""
    logger.info("Starting workflow run for %s", req.repo_path)
    
    # We run the workflow in a background task to not block the request
    asyncio.create_task(execute_workflow(req))
    
    return {"message": "Workflow started", "repo_path": req.repo_path}

async def execute_workflow(req: runRequest):
    """Internal runner that streams LangGraph state updates."""
    workflow = build_workflow()

    resolved_target = req.deploy_target or _detect_deploy_target(req.deploy_prompt)

    initial_state: BugRewindState = {
        "repo_path": req.repo_path,
        "deploy_prompt": req.deploy_prompt,
        "deploy_target": resolved_target,
        "codebase": "",
        "file_manifest": {},
        "plan": "",
        "issues": [],
        "current_issues": [],
        "patches": [],
        "last_patch_count": 0,
        "iteration": 0,
        "max_iterations": req.max_iterations,
        "build_attempts": 0,
        "dockerfile": "",
        "dockerignore": "",
        "docker_build_log": "",
        "docker_run_log": "",
        "docker_status": "",
        "vercel_json": "",
        "vercel_deploy_url": "",
        "vercel_deploy_log": "",
        "vercel_status": "",
        "logs": "[BugRewind] Dashboard-triggered workflow started.",
        "summary": "",
    }

    try:
        # We use astream to get node-by-node updates
        async for event in workflow.astream(initial_state, stream_mode="updates"):
            # event is a dict: {node_name: {state_updates}}
            node_name = list(event.keys())[0]
            updates = event[node_name]
            
            # Broadcast the update
            await manager.broadcast({
                "type": "node_update",
                "node": node_name,
                "updates": serialize_state(updates)
            })
            
            # Small delay to make visualization smoother
            await asyncio.sleep(0.5)

        await manager.broadcast({"type": "workflow_complete", "status": "finished"})
        
    except Exception as e:
        logger.exception("Workflow iteration failed")
        await manager.broadcast({
            "type": "error",
            "message": str(e)
        })

def serialize_state(state: Dict[str, Any]) -> Dict[str, Any]:
    """Basic cleanup to ensure JSON serializability for the frontend."""
    # Annotations and complex types might need handling, but strings/lists/dicts are fine.
    # We'll just return it as is for now as pydantic handles it usually.
    return state

@app.get("/api/watcher/containers")
async def get_watcher_containers():
    """Retrieve all monitored containers and watcher statistics."""
    from bugrewind.utils.db import get_all_containers
    try:
        containers = get_all_containers()
        
        # Calculate some basic metrics
        total = len(containers)
        monitoring = sum(1 for c in containers if c['status'] == 'monitoring')
        analyzing = sum(1 for c in containers if c['status'] == 'analyzing')
        notified = sum(1 for c in containers if c['status'] == 'notified')
        lost = sum(1 for c in containers if c['status'] == 'lost')
        
        metrics = {
            "totalDeployments": total,
            "activeMonitoring": monitoring,
            "incidentsAnalyzed": notified + analyzing,
            "containersLost": lost
        }
        
        return {
            "containers": containers,
            "metrics": metrics
        }
    except Exception as e:
        logger.error(f"Error fetching containers: {e}")
        return {"containers": [], "metrics": {}}

@app.delete("/api/watcher/containers/{container_id}")
async def delete_watcher_container(container_id: str):
    """Delete a monitored container entry."""
    from bugrewind.utils.db import delete_container
    try:
        delete_container(container_id)
        return {"status": "success", "message": f"Container {container_id} deleted."}
    except Exception as e:
        logger.error(f"Error deleting container: {e}")
        return {"status": "error", "message": str(e)}

@app.post("/api/watcher/containers/{container_id}/start")
async def start_watcher_container(container_id: str):
    """Start a docker container by its docker container_id."""
    import docker
    from bugrewind.utils.db import _get_connection
    try:
        client = docker.from_env()
        # Find exactly the container using container_id
        container = client.containers.get(container_id)
        container.start()
        
        # Reset status back to 'monitoring' so the watcher daemon picks it up again
        conn = _get_connection()
        conn.execute("UPDATE containers SET status = 'monitoring' WHERE container_id = ?", (container_id,))
        conn.commit()
        conn.close()
        
        return {"status": "success", "message": f"Container {container_id} started and monitoring resumed."}
    except Exception as e:
        logger.error(f"Error starting container {container_id}: {e}")
        return {"status": "error", "message": str(e)}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
