#!/usr/bin/env python3
"""Launch the local SEO dashboard without typing server commands."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import socket
import subprocess
import sys
import time
import webbrowser


ROOT = Path(__file__).resolve().parents[2]
APP_DIR = Path(__file__).resolve().parent
PID_FILE = ROOT / ".dashboard_server.pid"
OUT_LOG = APP_DIR / "server.out.log"
ERR_LOG = APP_DIR / "server.err.log"
DEFAULT_PORT = 8766


def is_port_open(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.4)
        return sock.connect_ex(("127.0.0.1", port)) == 0


def windows_port_pid(port: int) -> int | None:
    if os.name != "nt":
        return None
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


def python_executable() -> str:
    current = Path(sys.executable)
    python_exe = current.with_name("python.exe")
    if python_exe.exists():
        return str(python_exe)
    return sys.executable


def start_server(port: int) -> int:
    OUT_LOG.parent.mkdir(parents=True, exist_ok=True)
    out = OUT_LOG.open("a", encoding="utf-8")
    err = ERR_LOG.open("a", encoding="utf-8")
    creationflags = 0
    if os.name == "nt":
        creationflags = subprocess.CREATE_NO_WINDOW
    process = subprocess.Popen(
        [python_executable(), "-u", "apps/seo_dashboard/server.py", str(port)],
        cwd=str(ROOT),
        stdout=out,
        stderr=err,
        creationflags=creationflags,
    )
    PID_FILE.write_text(str(process.pid), encoding="ascii")
    return process.pid


def wait_until_ready(port: int, seconds: float = 6.0) -> bool:
    deadline = time.time() + seconds
    while time.time() < deadline:
        if is_port_open(port):
            return True
        time.sleep(0.25)
    return False


def main() -> int:
    parser = argparse.ArgumentParser(description="Launch local SEO dashboard.")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args()

    url = f"http://127.0.0.1:{args.port}"
    if is_port_open(args.port):
        pid = windows_port_pid(args.port)
        if pid:
            PID_FILE.write_text(str(pid), encoding="ascii")
        if not args.no_browser:
            webbrowser.open(url)
        print(f"SEO dashboard is already running: {url}")
        return 0

    PID_FILE.unlink(missing_ok=True)
    pid = start_server(args.port)
    if not wait_until_ready(args.port):
        print("Dashboard did not become ready. Check logs:")
        print(OUT_LOG)
        print(ERR_LOG)
        return 1

    actual_pid = windows_port_pid(args.port)
    if actual_pid:
        pid = actual_pid
        PID_FILE.write_text(str(pid), encoding="ascii")

    if not args.no_browser:
        webbrowser.open(url)
    print(f"SEO dashboard started: {url}")
    print(f"PID: {pid}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
