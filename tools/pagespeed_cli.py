#!/usr/bin/env python3
"""Compatibility CLI for the canonical SEO-053 PageSpeed service."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from apps.api.core.config import load_env, mask_secret
from apps.api.services.pagespeed_service import DEFAULT_CATEGORIES, analyze


def print_json(data: object) -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    print(json.dumps(data, ensure_ascii=False, indent=2))


def command_check_env(args: argparse.Namespace) -> None:
    del args
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
    categories = args.categories or [item.strip() for item in env.get("PAGESPEED_DEFAULT_CATEGORIES", ",".join(DEFAULT_CATEGORIES)).split(",") if item.strip()]
    try:
        result = analyze(url, [strategy], categories, args.locale)
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc
    # The canonical service validates and persists before returning success.
    # --save remains accepted for backward compatibility but is no longer a
    # separate persistence path.
    print_json(result)
    if result.get("status") == "error":
        raise SystemExit(1)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="PageSpeed Insights CLI backed by the FastAPI service contract.")
    sub = parser.add_subparsers(dest="command", required=True)
    check = sub.add_parser("check-env")
    check.set_defaults(func=command_check_env)
    run = sub.add_parser("run")
    run.add_argument("--url", default="")
    run.add_argument("--strategy", choices=["mobile", "desktop"], default="")
    run.add_argument("--categories", nargs="+", default=[])
    run.add_argument("--locale", default="zh-CN")
    run.add_argument("--save", action="store_true")
    run.add_argument("--summary", action="store_true")
    run.set_defaults(func=command_run)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
