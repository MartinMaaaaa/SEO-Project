#!/usr/bin/env python3
"""Google Analytics 4 Data API CLI for the SEO dashboard."""

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
TOKEN_URL = "https://oauth2.googleapis.com/token"
API_BASE = "https://analyticsdata.googleapis.com/v1beta"
ADMIN_BASE = "https://analyticsadmin.googleapis.com/v1beta"


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
        if key.startswith(("GA4_", "GSC_")):
            env[key] = value
    return env


def mask_secret(value: str) -> str:
    if not value:
        return ""
    if len(value) <= 8:
        return "***"
    return value[:4] + "..." + value[-4:]


def require(keys: list[str], env: dict[str, str]) -> None:
    missing = [key for key in keys if not env.get(key)]
    if missing:
        raise SystemExit("Missing required environment variables: " + ", ".join(missing))


def client_values(env: dict[str, str]) -> tuple[str, str, str]:
    client_id = env.get("GA4_OAUTH_CLIENT_ID") or env.get("GSC_OAUTH_CLIENT_ID", "")
    client_secret = env.get("GA4_OAUTH_CLIENT_SECRET") or env.get("GSC_OAUTH_CLIENT_SECRET", "")
    refresh_token = env.get("GA4_OAUTH_REFRESH_TOKEN", "")
    if not client_id:
        raise SystemExit("Missing GA4_OAUTH_CLIENT_ID or GSC_OAUTH_CLIENT_ID")
    if not client_secret:
        raise SystemExit("Missing GA4_OAUTH_CLIENT_SECRET or GSC_OAUTH_CLIENT_SECRET")
    if not refresh_token:
        raise SystemExit("Missing GA4_OAUTH_REFRESH_TOKEN")
    return client_id, client_secret, refresh_token


def http_json(method: str, url: str, token: str | None = None, payload: dict[str, Any] | None = None, form: dict[str, str] | None = None) -> dict[str, Any]:
    headers = {"Accept": "application/json"}
    body: bytes | None = None
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if payload is not None:
        headers["Content-Type"] = "application/json"
        body = json.dumps(payload).encode("utf-8")
    if form is not None:
        headers["Content-Type"] = "application/x-www-form-urlencoded"
        body = parse.urlencode(form).encode("utf-8")
    req = request.Request(url, data=body, headers=headers, method=method)
    try:
        with request.urlopen(req, timeout=60) as response:
            text = response.read().decode("utf-8")
            return json.loads(text) if text else {}
    except error.HTTPError as exc:
        details = exc.read().decode("utf-8", errors="replace")
        raise SystemExit(f"HTTP {exc.code} from {url}\n{details}") from exc
    except error.URLError as exc:
        raise SystemExit(f"Network error calling {url}: {exc}") from exc


def access_token(env: dict[str, str]) -> str:
    client_id, client_secret, refresh_token = client_values(env)
    data = http_json(
        "POST",
        TOKEN_URL,
        form={
            "client_id": client_id,
            "client_secret": client_secret,
            "refresh_token": refresh_token,
            "grant_type": "refresh_token",
        },
    )
    token = str(data.get("access_token") or "")
    if not token:
        raise SystemExit("Could not refresh GA4 access token.")
    return token


def print_json(data: object) -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    print(json.dumps(data, ensure_ascii=False, indent=2))


def write_env_value(key: str, value: str, path: Path = ENV_PATH) -> None:
    lines = path.read_text(encoding="utf-8").splitlines() if path.exists() else []
    prefix = f"{key}="
    updated = False
    for index, line in enumerate(lines):
        if line.startswith(prefix):
            lines[index] = prefix + value
            updated = True
            break
    if not updated:
        lines.append(prefix + value)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def command_check_env(args: argparse.Namespace) -> None:
    env = load_env()
    keys = ["GA4_PROPERTY_ID", "GA4_OAUTH_CLIENT_ID", "GA4_OAUTH_CLIENT_SECRET", "GA4_OAUTH_REFRESH_TOKEN", "GA4_CACHE_DIR"]
    result = {}
    for key in keys:
        value = env.get(key, "")
        result[key] = {"configured": bool(value), "value": mask_secret(value) if "SECRET" in key or "TOKEN" in key else value}
    print_json(result)


def command_token(args: argparse.Namespace) -> None:
    token = access_token(load_env())
    print_json({"status": "ok", "access_token": mask_secret(token)})


def command_properties(args: argparse.Namespace) -> None:
    token = access_token(load_env())
    data = http_json("GET", f"{ADMIN_BASE}/accountSummaries", token=token)
    properties = []
    for account in data.get("accountSummaries", []):
        for prop in account.get("propertySummaries", []):
            property_name = str(prop.get("property", ""))
            properties.append(
                {
                    "account": account.get("displayName", ""),
                    "accountResource": account.get("account", ""),
                    "property": prop.get("displayName", ""),
                    "propertyResource": property_name,
                    "propertyId": property_name.split("/")[-1],
                }
            )
    print_json({"properties": properties, "count": len(properties)})


def command_use_property(args: argparse.Namespace) -> None:
    property_id = args.property_id.strip().replace("properties/", "")
    if not property_id.isdigit():
        raise SystemExit("GA4 property ID must be numeric, for example 123456789.")
    write_env_value("GA4_PROPERTY_ID", property_id)
    print_json({"updated": True, "GA4_PROPERTY_ID": property_id})


def command_report(args: argparse.Namespace) -> None:
    env = load_env()
    require(["GA4_PROPERTY_ID"], env)
    token = access_token(env)
    body = {
        "dateRanges": [{"startDate": args.start, "endDate": args.end}],
        "dimensions": [{"name": item} for item in args.dimensions],
        "metrics": [{"name": item} for item in args.metrics],
        "limit": str(args.limit),
    }
    if args.organic_only:
        body["dimensionFilter"] = {
            "filter": {
                "fieldName": "sessionDefaultChannelGroup",
                "stringFilter": {"matchType": "EXACT", "value": "Organic Search"},
            }
        }
    url = f"{API_BASE}/properties/{env['GA4_PROPERTY_ID']}:runReport"
    data = http_json("POST", url, token=token, payload=body)
    if args.save:
        save_report(data, body, env)
    if not args.quiet:
        print_json(data)


def save_report(data: dict[str, Any], body: dict[str, Any], env: dict[str, str]) -> None:
    cache = ROOT / env.get("GA4_CACHE_DIR", "data/ga4") / "raw"
    cache.mkdir(parents=True, exist_ok=True)
    stamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    dims = "-".join(item["name"] for item in body.get("dimensions", [])) or "summary"
    start = body["dateRanges"][0]["startDate"]
    end = body["dateRanges"][0]["endDate"]
    path = cache / f"ga4_{env['GA4_PROPERTY_ID']}_{start}_{end}_{dims}_{stamp}.json"
    path.write_text(json.dumps({"request": body, "response": data}, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Saved: {path}")


def default_dates() -> tuple[str, str]:
    end = dt.date.today() - dt.timedelta(days=1)
    start = end - dt.timedelta(days=27)
    return start.isoformat(), end.isoformat()


def build_parser() -> argparse.ArgumentParser:
    start, end = default_dates()
    parser = argparse.ArgumentParser(description="GA4 Data API CLI.")
    sub = parser.add_subparsers(dest="command", required=True)
    check = sub.add_parser("check-env")
    check.set_defaults(func=command_check_env)
    token = sub.add_parser("token")
    token.set_defaults(func=command_token)
    properties = sub.add_parser("properties", help="List GA4 properties accessible to the authorized user.")
    properties.set_defaults(func=command_properties)
    use_property = sub.add_parser("use-property", help="Write the selected GA4 property ID to .env.")
    use_property.add_argument("--property-id", required=True)
    use_property.set_defaults(func=command_use_property)
    report = sub.add_parser("report")
    report.add_argument("--start", default=start)
    report.add_argument("--end", default=end)
    report.add_argument("--dimensions", nargs="+", default=["date", "sessionDefaultChannelGroup"])
    report.add_argument("--metrics", nargs="+", default=["sessions", "totalUsers", "activeUsers", "screenPageViews", "engagedSessions"])
    report.add_argument("--limit", type=int, default=1000)
    report.add_argument("--organic-only", action="store_true")
    report.add_argument("--save", action="store_true")
    report.add_argument("--quiet", action="store_true")
    report.set_defaults(func=command_report)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
