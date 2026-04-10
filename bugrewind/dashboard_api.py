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

from bugrewind.graph.workflow import build_workflow
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
    def _open_dialog():
        import tkinter as tk
        from tkinter import filedialog
        root = tk.Tk()
        root.withdraw()
        root.attributes("-topmost", True)
        folder = filedialog.askdirectory(parent=root, title="Select Repository Folder")
        root.destroy()
        return folder
    loop = asyncio.get_running_loop()
    folder_path = await loop.run_in_executor(None, _open_dialog)
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
    
    initial_state: BugRewindState = {
        "repo_path": req.repo_path,
        "deploy_prompt": req.deploy_prompt,
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

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
