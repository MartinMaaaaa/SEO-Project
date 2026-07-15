#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
from urllib.request import urlopen
import webbrowser

ROOT = Path(__file__).resolve().parents[2]
PID_FILE = ROOT / "data" / "local" / "separated_stack.pid"
LOG_DIR = ROOT / "data" / "logs"
API_URL = "http://127.0.0.1:8787"
WEB_URL = "http://127.0.0.1:5173"


def healthy(url: str) -> bool:
    try:
        with urlopen(url, timeout=2) as response:
            return response.status == 200
    except Exception:
        return False


def main() -> int:
    parser = argparse.ArgumentParser(description="Start the separated React and FastAPI stack.")
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args()
    node = shutil.which("node")
    vite = ROOT / "apps" / "web" / "node_modules" / "vite" / "bin" / "vite.js"
    if not node or not vite.exists():
        print("Frontend runtime is missing. Install Node.js, then run npm.cmd install in apps/web.")
        return 1
    if healthy(API_URL + "/api/health") and healthy(WEB_URL):
        print(f"React and FastAPI are already running at {WEB_URL} and {API_URL}")
        if not args.no_browser: webbrowser.open(WEB_URL)
        return 0

    LOG_DIR.mkdir(parents=True, exist_ok=True)
    PID_FILE.parent.mkdir(parents=True, exist_ok=True)
    flags = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0) | getattr(subprocess, "DETACHED_PROCESS", 0)
    api_out = (LOG_DIR / "api.out.log").open("a", encoding="utf-8")
    api_err = (LOG_DIR / "api.err.log").open("a", encoding="utf-8")
    web_out = (LOG_DIR / "web.out.log").open("a", encoding="utf-8")
    web_err = (LOG_DIR / "web.err.log").open("a", encoding="utf-8")
    api = subprocess.Popen([sys.executable, "-m", "uvicorn", "apps.api.main:app", "--host", "127.0.0.1", "--port", "8787"], cwd=ROOT, stdin=subprocess.DEVNULL, stdout=api_out, stderr=api_err, creationflags=flags, close_fds=True)
    web = subprocess.Popen([node, str(vite), "--host", "127.0.0.1", "--port", "5173", "--strictPort"], cwd=ROOT / "apps" / "web", stdin=subprocess.DEVNULL, stdout=web_out, stderr=web_err, creationflags=flags, close_fds=True)
    PID_FILE.write_text(json.dumps({"api": api.pid, "web": web.pid}), encoding="utf-8")
    for _ in range(60):
        if healthy(API_URL + "/api/health") and healthy(WEB_URL):
            print(f"React frontend: {WEB_URL}")
            print(f"FastAPI backend: {API_URL}")
            if not args.no_browser: webbrowser.open(WEB_URL)
            return 0
        if api.poll() is not None or web.poll() is not None: break
        time.sleep(0.25)
    print("Startup failed. Check data/logs/api.err.log and data/logs/web.err.log.")
    return 1


if __name__ == "__main__": raise SystemExit(main())
