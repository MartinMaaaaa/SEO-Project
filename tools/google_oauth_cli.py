#!/usr/bin/env python3
"""Small OAuth helper for Google SEO data connectors.

It writes refresh tokens into .env without printing secrets.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from urllib import error, parse, request


ROOT = Path(__file__).resolve().parents[1]
ENV_PATH = ROOT / ".env"
AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"

SCOPES = {
    "gsc": "https://www.googleapis.com/auth/webmasters.readonly",
    "ga4": "https://www.googleapis.com/auth/analytics.readonly",
    "gsc_ga4": "https://www.googleapis.com/auth/webmasters.readonly https://www.googleapis.com/auth/analytics.readonly",
}


def load_env() -> dict[str, str]:
    values: dict[str, str] = {}
    if ENV_PATH.exists():
        for raw_line in ENV_PATH.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            values[key.strip()] = value.strip().strip('"').strip("'")
    for key, value in os.environ.items():
        if key.startswith(("GSC_", "GA4_")):
            values[key] = value
    return values


def write_env_value(key: str, value: str) -> None:
    lines = ENV_PATH.read_text(encoding="utf-8").splitlines() if ENV_PATH.exists() else []
    prefix = f"{key}="
    updated = False
    for index, line in enumerate(lines):
        if line.startswith(prefix):
            lines[index] = prefix + value
            updated = True
            break
    if not updated:
        lines.append(prefix + value)
    ENV_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def mask_secret(value: str) -> str:
    if not value:
        return ""
    if len(value) <= 8:
        return "***"
    return value[:4] + "..." + value[-4:]


def client_values(env: dict[str, str], target: str) -> tuple[str, str]:
    client_id = env.get("GA4_OAUTH_CLIENT_ID") or env.get("GSC_OAUTH_CLIENT_ID", "")
    client_secret = env.get("GA4_OAUTH_CLIENT_SECRET") or env.get("GSC_OAUTH_CLIENT_SECRET", "")
    if target == "gsc":
        client_id = env.get("GSC_OAUTH_CLIENT_ID") or client_id
        client_secret = env.get("GSC_OAUTH_CLIENT_SECRET") or client_secret
    missing = []
    if not client_id:
        missing.append("GSC_OAUTH_CLIENT_ID or GA4_OAUTH_CLIENT_ID")
    if not client_secret:
        missing.append("GSC_OAUTH_CLIENT_SECRET or GA4_OAUTH_CLIENT_SECRET")
    if missing:
        raise SystemExit("Missing: " + ", ".join(missing))
    return client_id, client_secret


def http_json(form: dict[str, str]) -> dict[str, object]:
    req = request.Request(
        TOKEN_URL,
        data=parse.urlencode(form).encode("utf-8"),
        headers={"Content-Type": "application/x-www-form-urlencoded", "Accept": "application/json"},
        method="POST",
    )
    try:
        with request.urlopen(req, timeout=60) as response:
            return json.loads(response.read().decode("utf-8"))
    except error.HTTPError as exc:
        details = exc.read().decode("utf-8", errors="replace")
        raise SystemExit(f"HTTP {exc.code}\n{details}") from exc
    except error.URLError as exc:
        raise SystemExit(f"Network error: {exc}") from exc


def command_copy_client(args: argparse.Namespace) -> None:
    env = load_env()
    client_id = env.get("GSC_OAUTH_CLIENT_ID", "")
    client_secret = env.get("GSC_OAUTH_CLIENT_SECRET", "")
    if not client_id or not client_secret:
        raise SystemExit("GSC OAuth client is not configured.")
    write_env_value("GA4_OAUTH_CLIENT_ID", client_id)
    write_env_value("GA4_OAUTH_CLIENT_SECRET", client_secret)
    print(json.dumps({"ok": True, "GA4_OAUTH_CLIENT_ID": mask_secret(client_id), "GA4_OAUTH_CLIENT_SECRET": mask_secret(client_secret)}, indent=2))


def command_auth_url(args: argparse.Namespace) -> None:
    env = load_env()
    client_id, _ = client_values(env, args.target)
    scope = args.scope or SCOPES[args.target]
    params = {
        "client_id": client_id,
        "redirect_uri": args.redirect_uri,
        "response_type": "code",
        "scope": scope,
        "access_type": "offline",
        "prompt": "consent",
    }
    print(AUTH_URL + "?" + parse.urlencode(params))


def command_exchange_code(args: argparse.Namespace) -> None:
    env = load_env()
    client_id, client_secret = client_values(env, args.target)
    data = http_json(
        {
            "code": args.code.strip().strip("、"),
            "client_id": client_id,
            "client_secret": client_secret,
            "redirect_uri": args.redirect_uri,
            "grant_type": "authorization_code",
        }
    )
    refresh_token = str(data.get("refresh_token") or "")
    if refresh_token:
        if args.target == "ga4":
            write_env_value("GA4_OAUTH_REFRESH_TOKEN", refresh_token)
        elif args.target == "gsc":
            write_env_value("GSC_OAUTH_REFRESH_TOKEN", refresh_token)
        else:
            write_env_value("GSC_OAUTH_REFRESH_TOKEN", refresh_token)
            write_env_value("GA4_OAUTH_REFRESH_TOKEN", refresh_token)
    print(
        json.dumps(
            {
                "ok": bool(refresh_token),
                "target": args.target,
                "refresh_token_written": bool(refresh_token),
                "scope": data.get("scope", ""),
                "access_token": mask_secret(str(data.get("access_token") or "")),
                "refresh_token": mask_secret(refresh_token),
            },
            indent=2,
        )
    )
    if not refresh_token:
        print("No refresh_token returned. Generate a new auth URL and authorize again.")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Google OAuth helper for SEO APIs.")
    sub = parser.add_subparsers(dest="command", required=True)

    copy_client = sub.add_parser("copy-gsc-client-to-ga4", help="Copy existing GSC OAuth client ID/secret to GA4 env fields.")
    copy_client.set_defaults(func=command_copy_client)

    auth_url = sub.add_parser("auth-url", help="Print OAuth consent URL.")
    auth_url.add_argument("--target", choices=["gsc", "ga4", "gsc_ga4"], default="ga4")
    auth_url.add_argument("--scope", default="")
    auth_url.add_argument("--redirect-uri", default="http://localhost:8765/oauth2callback")
    auth_url.set_defaults(func=command_auth_url)

    exchange = sub.add_parser("exchange-code", help="Exchange authorization code and write refresh token to .env.")
    exchange.add_argument("--target", choices=["gsc", "ga4", "gsc_ga4"], default="ga4")
    exchange.add_argument("--code", required=True)
    exchange.add_argument("--redirect-uri", default="http://localhost:8765/oauth2callback")
    exchange.set_defaults(func=command_exchange_code)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    args.func(args)


if __name__ == "__main__":
    main()

