#!/usr/bin/env python3
"""PageSpeed Insights API CLI."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
from pathlib import Path
import sys
from typing import Any
from urllib import error, parse, request


ROOT = Path(__file__).resolve().parents[1]
ENV_PATH = ROOT / ".env"
API_URL = "https://www.googleapis.com/pagespeedonline/v5/runPagespeed"


def load_env() -> dict[str, str]:
    env: dict[str, str] = {}
    if ENV_PATH.exists():
        for raw_line in ENV_PATH.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            env[key.strip()] = value.strip().strip('"').strip("'")
    for key, value in os.environ.items():
        if key.startswith(("PAGESPEED_", "SITE_")):
            env[key] = value
    return env


def mask_secret(value: str) -> str:
    if not value:
        return ""
    return value[:4] + "..." + value[-4:] if len(value) > 8 else "***"


def http_json(url: str) -> dict[str, Any]:
    req = request.Request(url, headers={"Accept": "application/json"}, method="GET")
    try:
        with request.urlopen(req, timeout=120) as response:
            return json.loads(response.read().decode("utf-8"))
    except error.HTTPError as exc:
        details = exc.read().decode("utf-8", errors="replace")
        raise SystemExit(f"HTTP {exc.code} from {redact_url(url)}\n{details}") from exc
    except error.URLError as exc:
        raise SystemExit(f"Network error calling {redact_url(url)}: {exc}") from exc


def redact_url(url: str) -> str:
    parsed = parse.urlparse(url)
    params = parse.parse_qsl(parsed.query, keep_blank_values=True)
    safe_params = [(key, "REDACTED" if key == "key" else value) for key, value in params]
    return parse.urlunparse(parsed._replace(query=parse.urlencode(safe_params)))


def print_json(data: object) -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    print(json.dumps(data, ensure_ascii=False, indent=2))


def command_check_env(args: argparse.Namespace) -> None:
    env = load_env()
    result = {}
    for key in ["PAGESPEED_API_KEY", "PAGESPEED_DEFAULT_STRATEGY", "PAGESPEED_DEFAULT_CATEGORIES", "PAGESPEED_CACHE_DIR", "SITE_CANONICAL_HOST"]:
        value = env.get(key, "")
        result[key] = {"configured": bool(value), "value": mask_secret(value) if "API_KEY" in key else value}
    print_json(result)


def command_run(args: argparse.Namespace) -> None:
    env = load_env()
    url = args.url or env.get("SITE_CANONICAL_HOST", "")
    if not url:
        raise SystemExit("Missing URL. Use --url or set SITE_CANONICAL_HOST.")
    strategy = args.strategy or env.get("PAGESPEED_DEFAULT_STRATEGY", "mobile")
    categories = args.categories or [item.strip() for item in env.get("PAGESPEED_DEFAULT_CATEGORIES", "performance,seo").split(",") if item.strip()]
    params: list[tuple[str, str]] = [("url", url), ("strategy", strategy)]
    for category in categories:
        params.append(("category", category))
    key = env.get("PAGESPEED_API_KEY", "")
    if key:
        params.append(("key", key))
    api_url = API_URL + "?" + parse.urlencode(params)
    data = http_json(api_url)
    summary = summarize(data)
    if args.save:
        save_result(data, summary, env, url, strategy)
    if args.summary:
        print_json(summary)
    else:
        print_json(data)


def summarize(data: dict[str, Any]) -> dict[str, Any]:
    lighthouse = data.get("lighthouseResult", {})
    categories = lighthouse.get("categories", {})
    audits = lighthouse.get("audits", {})
    return {
        "requestedUrl": data.get("id", ""),
        "finalUrl": lighthouse.get("finalDisplayedUrl", ""),
        "fetchTime": lighthouse.get("fetchTime", ""),
        "scores": {name: round((item.get("score") or 0) * 100, 2) for name, item in categories.items()},
        "coreMetrics": {
            "largest-contentful-paint": audits.get("largest-contentful-paint", {}).get("displayValue", ""),
            "total-blocking-time": audits.get("total-blocking-time", {}).get("displayValue", ""),
            "cumulative-layout-shift": audits.get("cumulative-layout-shift", {}).get("displayValue", ""),
            "speed-index": audits.get("speed-index", {}).get("displayValue", ""),
        },
    }


def save_result(data: dict[str, Any], summary: dict[str, Any], env: dict[str, str], url: str, strategy: str) -> None:
    cache = ROOT / env.get("PAGESPEED_CACHE_DIR", "data/pagespeed") / "raw"
    cache.mkdir(parents=True, exist_ok=True)
    stamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_url = "".join(ch if ch.isalnum() else "-" for ch in url).strip("-")[:80]
    path = cache / f"pagespeed_{safe_url}_{strategy}_{stamp}.json"
    path.write_text(json.dumps({"summary": summary, "response": data}, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Saved: {path}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="PageSpeed Insights CLI.")
    sub = parser.add_subparsers(dest="command", required=True)
    check = sub.add_parser("check-env")
    check.set_defaults(func=command_check_env)
    run = sub.add_parser("run")
    run.add_argument("--url", default="")
    run.add_argument("--strategy", choices=["mobile", "desktop"], default="")
    run.add_argument("--categories", nargs="+", default=[])
    run.add_argument("--save", action="store_true")
    run.add_argument("--summary", action="store_true")
    run.set_defaults(func=command_run)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
