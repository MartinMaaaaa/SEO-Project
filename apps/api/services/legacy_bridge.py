from __future__ import annotations

from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[3]
LEGACY_APP = ROOT / "apps" / "seo_dashboard"
if str(LEGACY_APP) not in sys.path:
    sys.path.insert(0, str(LEGACY_APP))

import server as legacy_server  # noqa: E402


def status() -> dict[str, Any]:
    return {"env": legacy_server.load_env_masked(), "exports": legacy_server.gsc_exports()[:10]}


def gsc_explorer(params: dict[str, list[str]]) -> dict[str, Any]:
    return legacy_server.gsc_explorer(params)


def ga4_analytics(params: dict[str, list[str]]) -> dict[str, Any]:
    return legacy_server.ga4_analytics(params)


def pagespeed_history(params: dict[str, list[str]]) -> dict[str, Any]:
    return legacy_server.pagespeed_history(params)


def crux_summary() -> dict[str, Any]:
    return legacy_server.summarize_crux()


def sync_gsc() -> dict[str, Any]:
    return legacy_server.run_gsc_sync()


def sync_ga4() -> dict[str, Any]:
    return legacy_server.run_ga4_sync()


def sync_pagespeed(url: str = "", strategy: str = "") -> dict[str, Any]:
    return legacy_server.run_pagespeed_sync(url, strategy)


def sync_crux() -> dict[str, Any]:
    return legacy_server.run_crux_sync()
