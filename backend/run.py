"""Run the Northline API with uvicorn."""

from __future__ import annotations

import os
import socket
import subprocess
import sys
import time
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parent
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

import env_loader  # noqa: F401

import uvicorn

PORT = int(os.getenv("NORTHLINE_PORT", "8000"))


def _port_in_use(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.5)
        return sock.connect_ex(("127.0.0.1", port)) == 0


def _free_port_if_needed(port: int) -> None:
    auto_stop = os.getenv("NORTHLINE_AUTO_STOP", "1").strip().lower() in {"1", "true", "yes"}
    if not _port_in_use(port):
        return
    if not auto_stop:
        print(
            f"ERROR: Port {port} is already in use.\n"
            f"Run: cd backend && .\\stop.ps1\n"
            f"Or set NORTHLINE_AUTO_STOP=1 to auto-stop stale Northline processes."
        )
        sys.exit(1)

    stop_script = BACKEND_ROOT / "stop.ps1"
    if sys.platform == "win32" and stop_script.exists():
        print(f"Port {port} is in use — stopping stale Northline backend...")
        subprocess.run(
            ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(stop_script)],
            check=False,
        )
        time.sleep(2)
        if _port_in_use(port):
            print(f"ERROR: Port {port} is still in use. Close the other backend terminal and run .\\stop.ps1")
            sys.exit(1)
    else:
        print(f"ERROR: Port {port} is already in use. Stop the other process and try again.")
        sys.exit(1)


if __name__ == "__main__":
    _free_port_if_needed(PORT)

    # Reload spawns a parent + child process; on Windows stale children can keep
    # port 8000 and cause "backend offline" hangs. Set NORTHLINE_RELOAD=1 to enable.
    reload = os.getenv("NORTHLINE_RELOAD", "").strip().lower() in {"1", "true", "yes"}
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=PORT,
        reload=reload,
        app_dir=str(BACKEND_ROOT),
    )
