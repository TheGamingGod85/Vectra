"""
BugRewind GUI Launcher.

Starts the FastAPI backend and the Vite frontend dev server concurrently.
"""

import subprocess
import sys
import os
import time
import signal
from pathlib import Path

def launch():
    project_root = Path(__file__).parent.parent.resolve()
    dashboard_dir = project_root / "bugrewind" / "dashboard"
    
    print("☕ Starting BugRewind Dashboard...")
    
    # Start Backend
    print("➤ Launching Backend (FastAPI) on port 8000...")
    backend_proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "bugrewind.dashboard_api:app", "--reload"],
        cwd=project_root
    )
    
    # Start Frontend
    print("➤ Launching Frontend (Vite) on port 3000...")
    if not (dashboard_dir / "node_modules").exists():
        print("ℹ️ node_modules not found. Installing dependencies...")
        subprocess.run(["npm", "install"], cwd=dashboard_dir, shell=True)
    
    frontend_proc = subprocess.Popen(
        ["npm", "run", "dev"],
        cwd=dashboard_dir,
        shell=True
    )
    
    print("\n✅ Dashboard is warming up!")
    print("   🌐 View at: http://localhost:3000")
    print("   Press Ctrl+C to shut down.\n")
    
    try:
        while True:
            time.sleep(1)
            if backend_proc.poll() is not None:
                print("❌ Backend stopped.")
                break
            if frontend_proc.poll() is not None:
                print("❌ Frontend stopped.")
                break
    except KeyboardInterrupt:
        print("\nShutting down coffee machine...")
    finally:
        backend_proc.terminate()
        frontend_proc.terminate()

if __name__ == "__main__":
    launch()
