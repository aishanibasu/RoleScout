"""Start or reuse the local app and refresh worker, then open the browser."""

import argparse
import shutil
import socket
import subprocess
import sys
import time
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen

from .db import database_path
from .locks import AlreadyRunning, process_lock

ROOT = Path(__file__).resolve().parents[2]
URL = "http://localhost:5173"


def listening(port):
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=1):
            return True
    except OSError:
        return False


def ready(url, marker):
    try:
        with urlopen(url, timeout=2) as response:
            return marker in response.read().decode()
    except (OSError, URLError, UnicodeError):
        return False


def spawn(command, cwd, log):
    log.parent.mkdir(parents=True, exist_ok=True)
    with log.open("ab") as output:
        return subprocess.Popen(
            command,
            cwd=cwd,
            stdin=subprocess.DEVNULL,
            stdout=output,
            stderr=output,
            start_new_session=True,
        )


def ensure_service(port, url, marker, command, cwd, log):
    if listening(port):
        if ready(url, marker):
            print(f"Reusing RoleScout on port {port}.")
            return
        raise RuntimeError(
            f"Port {port} is occupied by another or unresponsive app. Nothing was stopped."
        )
    process = spawn(command, cwd, log)
    for _ in range(60):
        if ready(url, marker):
            print(f"RoleScout ready on port {port}.")
            return
        if process.poll() is not None:
            break
        time.sleep(0.5)
    raise RuntimeError(f"Startup failed or timed out. See {log}")


def ensure_scheduler(log):
    try:
        with process_lock(None, "scheduler"):
            pass
    except AlreadyRunning:
        print("Daily refresh worker is already running.")
        return
    process = spawn([sys.executable, "-m", "app.scheduler"], ROOT / "backend", log)
    for _ in range(20):
        try:
            with process_lock(None, "scheduler"):
                pass
        except AlreadyRunning:
            print("Daily refresh worker started; overdue sources will refresh in the background.")
            return
        if process.poll() is not None:
            break
        time.sleep(0.5)
    raise RuntimeError(f"Refresh worker did not start. See {log}")


def launch(open_browser=True):
    node = shutil.which("node")
    vite = ROOT / "frontend/node_modules/vite/bin/vite.js"
    if not node or not vite.is_file():
        raise RuntimeError(
            "Install Node.js and run pnpm install in frontend first. See README setup."
        )
    logs = database_path().parent / "logs"
    with process_lock(None, "launcher"):
        ensure_service(
            8000,
            "http://127.0.0.1:8000/openapi.json",
            '"title":"RoleScout API"',
            [
                sys.executable,
                "-m",
                "uvicorn",
                "app.main:app",
                "--host",
                "127.0.0.1",
                "--port",
                "8000",
            ],
            ROOT / "backend",
            logs / "api.log",
        )
        ensure_service(
            5173,
            "http://127.0.0.1:5173",
            "RoleScout — Find your next chapter",
            [node, str(vite), "--host", "127.0.0.1", "--port", "5173", "--strictPort"],
            ROOT / "frontend",
            logs / "frontend.log",
        )
        ensure_scheduler(logs / "scheduler.log")
    if open_browser:
        subprocess.run(["open", URL], check=True)
    print(f"RoleScout is ready: {URL}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args()
    try:
        launch(not args.no_browser)
    except (RuntimeError, OSError, subprocess.CalledProcessError) as error:
        print(f"Could not start RoleScout: {error}", file=sys.stderr)
        sys.exit(1)
