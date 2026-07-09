#!/usr/bin/env python3
"""Google Search Console CLI for AI-safe SEO workflows.

The tool uses only Python standard library modules. It reads OAuth settings from
.env, refreshes an access token, and queries the Google Search Console API.
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import os
from pathlib import Path
import sys
from typing import Any
from urllib import error, parse, request


ROOT = Path(__file__).resolve().parents[1]
ENV_PATH = ROOT / ".env"
DEFAULT_SCOPE = "https://www.googleapis.com/auth/webmasters.readonly"
TOKEN_URL = "https://oauth2.googleapis.com/token"
AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
API_BASE = "https://searchconsole.googleapis.com/webmasters/v3"
INSPECTION_URL = "https://searchconsole.googleapis.com/v1/urlInspection/index:inspect"


def load_env(path: Path = ENV_PATH) -> dict[str, str]:
    env: dict[str, str] = {}
    if path.exists():
        for raw_line in path.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            env[key.strip()] = value.strip().strip('"').strip("'")
    for key, value in os.environ.items():
        if key.startswith("GSC_"):
            env[key] = value
    return env


def require_env(env: dict[str, str], keys: list[str]) -> None:
    missing = [key for key in keys if not env.get(key)]
    if missing:
        raise SystemExit(
            "Missing required environment variables: "
            + ", ".join(missing)
            + "\nFill .env first. See .env.example and .ai/GSC_DATA_ACCESS.md."
        )


def http_json(
    method: str,
    url: str,
    token: str | None = None,
    payload: dict[str, Any] | None = None,
    form: dict[str, str] | None = None,
) -> dict[str, Any]:
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
    require_env(env, ["GSC_OAUTH_CLIENT_ID", "GSC_OAUTH_CLIENT_SECRET", "GSC_OAUTH_REFRESH_TOKEN"])
    data = http_json(
        "POST",
        TOKEN_URL,
        form={
            "client_id": env["GSC_OAUTH_CLIENT_ID"],
            "client_secret": env["GSC_OAUTH_CLIENT_SECRET"],
            "refresh_token": env["GSC_OAUTH_REFRESH_TOKEN"],
            "grant_type": "refresh_token",
        },
    )
    token = data.get("access_token")
    if not token:
        raise SystemExit(f"Could not refresh access token: {json.dumps(data, ensure_ascii=False)}")
    return str(token)


def print_json(data: Any) -> None:
    print(json.dumps(data, ensure_ascii=False, indent=2))


def masked_token_response(data: dict[str, Any]) -> dict[str, Any]:
    masked = dict(data)
    for key in ["access_token", "refresh_token", "id_token", "client_secret"]:
        if key in masked and isinstance(masked[key], str):
            masked[key] = mask_secret(masked[key])
    return masked


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
    keys = [
        "GSC_READONLY_SCOPE",
        "GSC_OAUTH_CLIENT_ID",
        "GSC_OAUTH_CLIENT_SECRET",
        "GSC_OAUTH_REFRESH_TOKEN",
        "GSC_SITE_URL",
        "GSC_CACHE_DIR",
    ]
    result = []
    for key in keys:
        value = env.get(key, "")
        result.append(
            {
                "key": key,
                "configured": bool(value),
                "value": mask_secret(value) if "SECRET" in key or "TOKEN" in key else value,
            }
        )
    print_json(result)


def mask_secret(value: str) -> str:
    if not value:
        return ""
    if len(value) <= 8:
        return "***"
    return value[:4] + "..." + value[-4:]


def command_auth_url(args: argparse.Namespace) -> None:
    env = load_env()
    require_env(env, ["GSC_OAUTH_CLIENT_ID"])
    scope = env.get("GSC_READONLY_SCOPE", DEFAULT_SCOPE)
    redirect_uri = args.redirect_uri
    params = {
        "client_id": env["GSC_OAUTH_CLIENT_ID"],
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": scope,
        "access_type": "offline",
        "prompt": "consent",
    }
    print(AUTH_URL + "?" + parse.urlencode(params))


def command_exchange_code(args: argparse.Namespace) -> None:
    env = load_env()
    require_env(env, ["GSC_OAUTH_CLIENT_ID", "GSC_OAUTH_CLIENT_SECRET"])
    data = http_json(
        "POST",
        TOKEN_URL,
        form={
            "code": args.code,
            "client_id": env["GSC_OAUTH_CLIENT_ID"],
            "client_secret": env["GSC_OAUTH_CLIENT_SECRET"],
            "redirect_uri": args.redirect_uri,
            "grant_type": "authorization_code",
        },
    )
    should_write_env = not args.no_write_env
    if should_write_env and data.get("refresh_token"):
        write_env_value("GSC_OAUTH_REFRESH_TOKEN", str(data["refresh_token"]))
    if args.print_json:
        print_json(data)
    else:
        result = masked_token_response(data)
        result["wrote_refresh_token_to_env"] = bool(should_write_env and data.get("refresh_token"))
        print_json(result)
    if "refresh_token" in data and not should_write_env:
        print("\nCopy refresh_token into GSC_OAUTH_REFRESH_TOKEN in .env.", file=sys.stderr)
    if "refresh_token" not in data:
        print("\nNo refresh_token returned. If one is already issued, generate a new auth URL with prompt=consent and try again.", file=sys.stderr)


def command_token(args: argparse.Namespace) -> None:
    env = load_env()
    token = access_token(env)
    print_json({"access_token": mask_secret(token), "status": "ok"})


def command_sites(args: argparse.Namespace) -> None:
    env = load_env()
    token = access_token(env)
    data = http_json("GET", f"{API_BASE}/sites", token=token)
    print_json(data)


def parse_filter(raw: str) -> dict[str, Any]:
    parts = raw.split(":", 2)
    if len(parts) != 3:
        raise argparse.ArgumentTypeError("Filter must be dimension:operator:expression")
    dimension, operator, expression = parts
    return {"dimension": dimension, "operator": operator, "expression": expression}


def command_performance(args: argparse.Namespace) -> None:
    env = load_env()
    token = access_token(env)
    site_url = args.site_url or env.get("GSC_SITE_URL")
    if not site_url:
        raise SystemExit("Missing site URL. Use --site-url or set GSC_SITE_URL in .env.")
    row_limit = min(args.row_limit, int(env.get("GSC_MAX_ROWS", "25000") or "25000"), 25000)
    body: dict[str, Any] = {
        "startDate": args.start,
        "endDate": args.end,
        "dimensions": args.dimensions,
        "type": args.search_type or env.get("GSC_DEFAULT_SEARCH_TYPE", "web"),
        "dataState": args.data_state or env.get("GSC_DEFAULT_DATA_STATE", "final"),
        "rowLimit": row_limit,
        "startRow": args.start_row,
    }
    filters = list(args.filter or [])
    country = args.country or env.get("GSC_DEFAULT_COUNTRY")
    if country:
        filters.append({"dimension": "country", "operator": "equals", "expression": country})
    if filters:
        body["dimensionFilterGroups"] = [{"filters": filters}]
    encoded_site = parse.quote(site_url, safe="")
    data = http_json("POST", f"{API_BASE}/sites/{encoded_site}/searchAnalytics/query", token=token, payload=body)
    if args.save:
        save_performance(data, body, site_url, args.output_format)
    if not args.quiet:
        print_json(data)


def save_performance(data: dict[str, Any], body: dict[str, Any], site_url: str, output_format: str) -> None:
    env = load_env()
    cache_dir = ROOT / env.get("GSC_CACHE_DIR", "data/gsc") / "raw"
    cache_dir.mkdir(parents=True, exist_ok=True)
    stamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    dims = "-".join(body.get("dimensions", [])) or "summary"
    safe_site = "".join(ch if ch.isalnum() else "-" for ch in site_url).strip("-")[:80]
    base = cache_dir / f"gsc_{safe_site}_{body['startDate']}_{body['endDate']}_{dims}_{stamp}"
    json_path = base.with_suffix(".json")
    json_path.write_text(json.dumps({"request": body, "siteUrl": site_url, "response": data}, ensure_ascii=False, indent=2), encoding="utf-8")
    if output_format == "csv":
        csv_path = base.with_suffix(".csv")
        rows_to_csv(data.get("rows", []), body.get("dimensions", []), csv_path)
        print(f"Saved: {json_path} and {csv_path}", file=sys.stderr)
    else:
        print(f"Saved: {json_path}", file=sys.stderr)


def rows_to_csv(rows: list[dict[str, Any]], dimensions: list[str], path: Path) -> None:
    fields = list(dimensions) + ["clicks", "impressions", "ctr", "position"]
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            values: dict[str, Any] = {}
            keys = row.get("keys", [])
            for index, dimension in enumerate(dimensions):
                values[dimension] = keys[index] if index < len(keys) else ""
            for metric in ["clicks", "impressions", "ctr", "position"]:
                values[metric] = row.get(metric, "")
            writer.writerow(values)


def command_inspect(args: argparse.Namespace) -> None:
    env = load_env()
    token = access_token(env)
    site_url = args.site_url or env.get("GSC_SITE_URL")
    if not site_url:
        raise SystemExit("Missing site URL. Use --site-url or set GSC_SITE_URL in .env.")
    body = {"inspectionUrl": args.url, "siteUrl": site_url}
    if args.language_code:
        body["languageCode"] = args.language_code
    data = http_json("POST", INSPECTION_URL, token=token, payload=body)
    print_json(data)


def default_dates() -> tuple[str, str]:
    end = dt.date.today() - dt.timedelta(days=3)
    start = end - dt.timedelta(days=27)
    return start.isoformat(), end.isoformat()


def build_parser() -> argparse.ArgumentParser:
    start, end = default_dates()
    parser = argparse.ArgumentParser(description="Google Search Console CLI for this SEO project.")
    sub = parser.add_subparsers(dest="command", required=True)

    check = sub.add_parser("check-env", help="Check local GSC environment variables.")
    check.set_defaults(func=command_check_env)

    auth = sub.add_parser("auth-url", help="Print OAuth consent URL for read-only GSC access.")
    auth.add_argument("--redirect-uri", default="http://localhost:8765/oauth2callback")
    auth.set_defaults(func=command_auth_url)

    exchange = sub.add_parser("exchange-code", help="Exchange OAuth code for tokens.")
    exchange.add_argument("--code", required=True)
    exchange.add_argument("--redirect-uri", default="http://localhost:8765/oauth2callback")
    exchange.add_argument("--write-env", action="store_true", help="Deprecated: refresh_token is written to .env by default.")
    exchange.add_argument("--no-write-env", action="store_true", help="Do not write refresh_token to .env.")
    exchange.add_argument("--print-json", action="store_true", help="Print the full token response. Avoid using this in AI sessions.")
    exchange.set_defaults(func=command_exchange_code)

    token = sub.add_parser("token", help="Test refresh-token access without printing the full token.")
    token.set_defaults(func=command_token)

    sites = sub.add_parser("sites", help="List Search Console sites available to the authorized user.")
    sites.set_defaults(func=command_sites)

    perf = sub.add_parser("performance", help="Query Search Analytics performance data.")
    perf.add_argument("--site-url", default="")
    perf.add_argument("--start", default=start)
    perf.add_argument("--end", default=end)
    perf.add_argument("--dimensions", nargs="+", default=["date", "query", "page"])
    perf.add_argument("--filter", action="append", type=parse_filter, help="dimension:operator:expression")
    perf.add_argument("--country", default="")
    perf.add_argument("--search-type", default="")
    perf.add_argument("--data-state", default="")
    perf.add_argument("--row-limit", type=int, default=25000)
    perf.add_argument("--start-row", type=int, default=0)
    perf.add_argument("--save", action="store_true")
    perf.add_argument("--quiet", action="store_true", help="Do not print rows to stdout. Useful with --save.")
    perf.add_argument("--output-format", choices=["json", "csv"], default="csv")
    perf.set_defaults(func=command_performance)

    inspect = sub.add_parser("inspect", help="Inspect a URL using the URL Inspection API.")
    inspect.add_argument("--url", required=True)
    inspect.add_argument("--site-url", default="")
    inspect.add_argument("--language-code", default="")
    inspect.set_defaults(func=command_inspect)

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
