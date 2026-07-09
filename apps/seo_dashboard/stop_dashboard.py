#!/usr/bin/env python3
"""Stop the local SEO dashboard process."""

from __future__ import annotations

from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[2]
PID_FILE = ROOT / ".dashboard_server.pid"
DEFAULT_PORT = 8766


def windows_port_pid(port: int) -> int | None:
    completed = subprocess.run(
        ["netstat", "-ano", "-p", "tcp"],
        text=True,
        capture_output=True,
        check=False,
    )
    suffix = f":{port}"
    for line in completed.stdout.splitlines():
        parts = line.split()
        if len(parts) >= 5 and parts[0].upper() == "TCP" and parts[1].endswith(suffix) and parts[3].upper() == "LISTENING":
            return int(parts[4]) if parts[4].isdigit() else None
    return None


def stop_windows_pid(pid: int) -> bool:
    completed = subprocess.run(
        ["taskkill", "/PID", str(pid), "/F"],
        text=True,
        capture_output=True,
        check=False,
    )
    return completed.returncode == 0


def main() -> int:
    if sys.platform.startswith("win"):
        pid: int | None = None
        if PID_FILE.exists():
            raw_pid = PID_FILE.read_text(encoding="ascii").strip()
            if raw_pid.isdigit():
                pid = int(raw_pid)
        if pid and stop_windows_pid(pid):
            print(f"Stopped SEO dashboard process {pid}.")
            PID_FILE.unlink(missing_ok=True)
            return 0
        port_pid = windows_port_pid(DEFAULT_PORT)
        if port_pid and stop_windows_pid(port_pid):
            print(f"Stopped SEO dashboard process {port_pid}.")
            PID_FILE.unlink(missing_ok=True)
            return 0
        print("Dashboard process is not running.")
        PID_FILE.unlink(missing_ok=True)
        return 0
    else:
        if not PID_FILE.exists():
            print("No dashboard pid file found.")
            return 0
        raw_pid = PID_FILE.read_text(encoding="ascii").strip()
        if not raw_pid.isdigit():
            print(f"Invalid pid file: {PID_FILE}")
            PID_FILE.unlink(missing_ok=True)
            return 1
        pid = int(raw_pid)
        import os
        import signal

        try:
            os.kill(pid, signal.SIGTERM)
            print(f"Stopped SEO dashboard process {pid}.")
        except ProcessLookupError:
            print(f"Dashboard process {pid} is not running.")

    PID_FILE.unlink(missing_ok=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
