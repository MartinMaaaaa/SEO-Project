#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys
import time
from urllib.request import urlopen
import webbrowser

ROOT = Path(__file__).resolve().parents[2]
PID_FILE = ROOT / "data" / "local" / "separated_stack.pid"
LOG_DIR = ROOT / "data" / "logs"
URL = "http://127.0.0.1:8787/"


def healthy() -> bool:
    try:
        with urlopen(URL + "api/health", timeout=2) as response:
            return response.status == 200 and bool(json.load(response).get("ok"))
    except Exception:
        return False


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args()
    if not (ROOT / "apps" / "web" / "dist" / "index.html").exists():
        print("Frontend build is missing. Run: cd apps/web && npm.cmd install && npm.cmd run build")
        return 1
    if healthy():
        print(f"SEO Data Console is already running at {URL}")
        if not args.no_browser: webbrowser.open(URL)
        return 0
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    PID_FILE.parent.mkdir(parents=True, exist_ok=True)
    out = (LOG_DIR / "api.out.log").open("a", encoding="utf-8")
    err = (LOG_DIR / "api.err.log").open("a", encoding="utf-8")
    flags = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0) | getattr(subprocess, "DETACHED_PROCESS", 0)
    process = subprocess.Popen([sys.executable, "-m", "uvicorn", "apps.api.main:app", "--host", "127.0.0.1", "--port", "8787"], cwd=ROOT, stdin=subprocess.DEVNULL, stdout=out, stderr=err, creationflags=flags, close_fds=True)
    PID_FILE.write_text(str(process.pid), encoding="utf-8")
    for _ in range(30):
        if healthy():
            print(f"SEO Data Console started at {URL}")
            if not args.no_browser: webbrowser.open(URL)
            return 0
        if process.poll() is not None: break
        time.sleep(0.25)
    print(f"Startup failed. Check {LOG_DIR / 'api.err.log'}")
    return 1


if __name__ == "__main__": raise SystemExit(main())
