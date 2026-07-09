#!/usr/bin/env python3
"""Chrome UX Report API CLI."""

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
API_URL = "https://chromeuxreport.googleapis.com/v1/records:queryRecord"


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
        if key.startswith(("CRUX_", "SITE_")):
            env[key] = value
    return env


def mask_secret(value: str) -> str:
    if not value:
        return ""
    return value[:4] + "..." + value[-4:] if len(value) > 8 else "***"


def http_json(url: str, payload: dict[str, Any]) -> dict[str, Any]:
    req = request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Accept": "application/json", "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with request.urlopen(req, timeout=60) as response:
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
    for key in ["CRUX_API_KEY", "CRUX_FORM_FACTOR", "CRUX_CACHE_DIR", "SITE_CANONICAL_HOST"]:
        value = env.get(key, "")
        result[key] = {"configured": bool(value), "value": mask_secret(value) if "API_KEY" in key else value}
    print_json(result)


def command_query(args: argparse.Namespace) -> None:
    env = load_env()
    key = env.get("CRUX_API_KEY", "")
    if not key:
        raise SystemExit("Missing CRUX_API_KEY")
    target = args.url or args.origin or env.get("SITE_CANONICAL_HOST", "")
    if not target:
        raise SystemExit("Missing target. Use --origin, --url, or set SITE_CANONICAL_HOST.")
    body: dict[str, Any] = {"url": target} if args.url else {"origin": target}
    form_factor = args.form_factor or env.get("CRUX_FORM_FACTOR", "")
    if form_factor and form_factor != "ALL":
        body["formFactor"] = form_factor
    url = API_URL + "?" + parse.urlencode({"key": key})
    data = http_json(url, body)
    summary = summarize(data)
    if args.save:
        save_result(data, summary, env, target, form_factor, "url" if args.url else "origin")
    if args.summary:
        print_json(summary)
    else:
        print_json(data)


def summarize(data: dict[str, Any]) -> dict[str, Any]:
    record = data.get("record", {})
    metrics = record.get("metrics", {})
    summary = {
        "key": record.get("key", {}),
        "collectionPeriod": record.get("collectionPeriod", {}),
        "metrics": {},
    }
    for name, metric in metrics.items():
        percentiles = metric.get("percentiles", {})
        histogram = metric.get("histogram", [])
        summary["metrics"][name] = {"p75": percentiles.get("p75"), "histogram": histogram}
    return summary


def save_result(data: dict[str, Any], summary: dict[str, Any], env: dict[str, str], target: str, form_factor: str, target_type: str) -> None:
    cache = ROOT / env.get("CRUX_CACHE_DIR", "data/crux") / "raw"
    cache.mkdir(parents=True, exist_ok=True)
    stamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_target = "".join(ch if ch.isalnum() else "-" for ch in target).strip("-")[:80]
    suffix = form_factor or "ALL"
    path = cache / f"crux_{target_type}_{safe_target}_{suffix}_{stamp}.json"
    path.write_text(json.dumps({"summary": summary, "response": data}, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Saved: {path}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Chrome UX Report CLI.")
    sub = parser.add_subparsers(dest="command", required=True)
    check = sub.add_parser("check-env")
    check.set_defaults(func=command_check_env)
    query = sub.add_parser("query")
    query.add_argument("--origin", default="")
    query.add_argument("--url", default="")
    query.add_argument("--form-factor", choices=["PHONE", "DESKTOP", "TABLET", "ALL", ""], default="")
    query.add_argument("--save", action="store_true")
    query.add_argument("--summary", action="store_true")
    query.set_defaults(func=command_query)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
