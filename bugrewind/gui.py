"""
BugRewind GUI Launcher.

Starts the FastAPI backend and the Vite frontend dev server concurrently.
"""

import subprocess
import sys
import time
import signal
from pathlib import Path


def _terminate_process(proc, name):
    if proc is None or proc.poll() is not None:
        return

    try:
        proc.terminate()
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        print(f"⚠️ {name} did not stop in time. Killing it...")
        proc.kill()
    except Exception as e:
        print(f"⚠️ Failed to stop {name}: {e}")


def launch():
    project_root = Path(__file__).parent.parent.resolve()
    dashboard_dir = project_root / "bugrewind" / "dashboard"

    print("☕ Starting BugRewind Dashboard...")

    if not dashboard_dir.exists():
        print(f"❌ Dashboard directory not found: {dashboard_dir}")
        sys.exit(1)

    if not (dashboard_dir / "package.json").exists():
        print(f"❌ package.json not found in: {dashboard_dir}")
        sys.exit(1)

    backend_proc = None
    frontend_proc = None

    try:
        # Start Backend
        print("➤ Launching Backend (FastAPI) on port 8000...")
        backend_proc = subprocess.Popen(
            [sys.executable, "-m", "uvicorn", "bugrewind.dashboard_api:app", "--reload"],
            cwd=project_root,
        )

        # Install frontend dependencies if needed
        print("➤ Launching Frontend (Vite) on port 3000...")
        if not (dashboard_dir / "node_modules").exists():
            print("ℹ️ node_modules not found. Installing dependencies...")
            subprocess.run(
                ["npm", "install"],
                cwd=dashboard_dir,
                check=True,
            )

        # Start Frontend
        frontend_proc = subprocess.Popen(
            ["npm", "run", "dev"],
            cwd=dashboard_dir,
        )

        print("\n✅ Dashboard is warming up!")
        print("   🌐 View at: http://localhost:3000")
        print("   Press Ctrl+C to shut down.\n")

        while True:
            time.sleep(1)

            if backend_proc.poll() is not None:
                print("❌ Backend stopped.")
                break

            if frontend_proc.poll() is not None:
                print("❌ Frontend stopped.")
                break

    except subprocess.CalledProcessError as e:
        print(f"❌ Command failed with exit code {e.returncode}: {e.cmd}")
        sys.exit(e.returncode)

    except KeyboardInterrupt:
        print("\nShutting down coffee machine...")

    finally:
        _terminate_process(frontend_proc, "Frontend")
        _terminate_process(backend_proc, "Backend")


if __name__ == "__main__":
    launch()