#!/usr/bin/env python3
from __future__ import annotations

import json
import os
from pathlib import Path
import signal
import subprocess
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[2]
PID_FILE = ROOT / "data" / "local" / "separated_stack.pid"


def stop_api() -> None:
    try:
        with urlopen(Request("http://127.0.0.1:8787/api/system/shutdown", method="POST"), timeout=3): pass
    except Exception:
        pass


def stop_process(pid: int) -> bool:
    try:
        os.kill(pid, signal.CTRL_BREAK_EVENT)
        return True
    except (AttributeError, OSError, SystemError):
        result = subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"], capture_output=True, text=True, check=False)
        if result.returncode in {0, 128}:
            return True
        listing = subprocess.run(["tasklist", "/FI", f"PID eq {pid}", "/NH"], capture_output=True, text=True, check=False)
        return str(pid) not in listing.stdout


def main() -> int:
    if not PID_FILE.exists():
        print("Separated React/FastAPI stack is not recorded as running.")
        return 0
    try:
        payload = json.loads(PID_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        PID_FILE.unlink(missing_ok=True)
        return 1
    stop_api()
    web_ok = stop_process(int(payload.get("web", 0))) if payload.get("web") else True
    PID_FILE.unlink(missing_ok=True)
    if not web_ok:
        print("FastAPI stopped, but the React process could not be stopped.")
        return 1
    print("React frontend and FastAPI backend stopped.")
    return 0


if __name__ == "__main__": raise SystemExit(main())
