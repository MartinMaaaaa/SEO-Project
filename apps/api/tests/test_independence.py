from __future__ import annotations

from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[3]


def test_active_source_has_no_legacy_runtime_reference() -> None:
    forbidden = ("apps/seo_dashboard", "legacy_bridge", "127.0.0.1:8766")
    for base in (ROOT / "apps" / "api", ROOT / "apps" / "web"):
        for path in base.rglob("*"):
            if path == Path(__file__) or not path.is_file() or "__pycache__" in path.parts or path.suffix not in {".py", ".ts", ".tsx", ".css", ".html", ".json", ".md"}:
                continue
            text = path.read_text(encoding="utf-8")
            assert not any(value in text for value in forbidden), f"forbidden runtime reference in {path}"


def test_backend_imports_and_reads_cache_when_legacy_access_is_blocked() -> None:
    script = r'''\
from pathlib import Path
original_open, original_exists, original_glob, original_iterdir = Path.open, Path.exists, Path.glob, Path.iterdir
def blocked(path): return "/apps/seo_dashboard" in str(path).replace("\\", "/").lower()
def guard(method):
    def wrapped(self, *args, **kwargs):
        if blocked(self): raise AssertionError(f"legacy access blocked: {self}")
        return method(self, *args, **kwargs)
    return wrapped
Path.open, Path.exists, Path.glob, Path.iterdir = guard(original_open), guard(original_exists), guard(original_glob), guard(original_iterdir)
from fastapi.testclient import TestClient
from apps.api.main import app
client = TestClient(app)
for endpoint in ("/api/health", "/api/status", "/api/storage/overview", "/api/gsc/explorer", "/api/ga4/analytics", "/api/pagespeed/history", "/api/crux/summary"):
    response = client.get(endpoint)
    assert response.status_code == 200, (endpoint, response.text)
'''
    result = subprocess.run([sys.executable, "-c", script], cwd=ROOT, capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stdout + result.stderr
