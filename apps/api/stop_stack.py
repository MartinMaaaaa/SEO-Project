#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import subprocess
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[2]
PID_FILE = ROOT / "data" / "local" / "separated_stack.pid"


def main() -> int:
    if not PID_FILE.exists():
        print("SEO Data Console is not recorded as running.")
        return 0
    try: pid = int(PID_FILE.read_text(encoding="utf-8").strip())
    except ValueError:
        PID_FILE.unlink(missing_ok=True); return 1
    try:
        with urlopen(Request("http://127.0.0.1:8787/api/system/shutdown", method="POST"), timeout=3) as response:
            if response.status == 200:
                PID_FILE.unlink(missing_ok=True)
                print("SEO Data Console stopped.")
                return 0
    except Exception:
        pass
    result = subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"], capture_output=True, text=True, check=False)
    PID_FILE.unlink(missing_ok=True)
    if result.returncode not in {0, 128}:
        print(result.stderr.strip() or result.stdout.strip())
        return 1
    print("SEO Data Console stopped.")
    return 0


if __name__ == "__main__": raise SystemExit(main())
