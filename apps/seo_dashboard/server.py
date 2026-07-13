#!/usr/bin/env python3
"""Local SEO dashboard server.

This server intentionally uses only the Python standard library. It exposes a
small local API for reading project files, summarizing cached GSC exports, and
triggering the existing read-only GSC CLI.
"""

from __future__ import annotations

import csv
import datetime as dt
import json
import mimetypes
from pathlib import Path
import re
import shutil
import subprocess
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib import parse

from cloud_sync import auto_upload_files, cloud_status, is_supabase_configured
from local_store import api_run_summary, api_source_status, latest_api_run, recent_api_runs, recent_pagespeed_runs, record_api_run, record_pagespeed_run, update_api_run_summary


ROOT = Path(__file__).resolve().parents[2]
APP_DIR = Path(__file__).resolve().parent / "static"
RAW_GSC_DIR = ROOT / "data" / "gsc" / "raw"
RAW_GA4_DIR = ROOT / "data" / "ga4" / "raw"
RAW_PAGESPEED_DIR = ROOT / "data" / "pagespeed" / "raw"
RAW_CRUX_DIR = ROOT / "data" / "crux" / "raw"
BACKUP_ROOT = ROOT / "data" / "backups" / "supabase_uploads"
AI_TASK_DIR = ROOT / ".ai" / "runtime_tasks"
SERVER_OUT_LOG = ROOT / "apps" / "seo_dashboard" / "server.out.log"
SERVER_ERR_LOG = ROOT / "apps" / "seo_dashboard" / "server.err.log"

DOCS = [
    {"id": "project_status", "title": "项目状态", "path": "PROJECT_STATUS.md", "type": "状态", "audience": "ops"},
    {"id": "readme", "title": "项目总览", "path": "README.md", "type": "总览", "audience": "ops"},
    {"id": "next_steps", "title": "下一步信息清单", "path": "NEXT_STEPS.md", "type": "计划", "audience": "ops"},
    {"id": "api_roadmap", "title": "API 接入路线图", "path": "API_ROADMAP.md", "type": "数据", "audience": "ops"},
    {"id": "backlog", "title": "SEO 任务池", "path": "backlog/seo_backlog.csv", "type": "任务", "audience": "ops"},
    {"id": "content_calendar", "title": "Blog 内容日历", "path": "02_content/blog_content_calendar.csv", "type": "内容", "audience": "ops"},
    {"id": "technical_audit", "title": "技术 SEO 检查清单", "path": "03_technical_seo/technical_audit_checklist.md", "type": "技术", "audience": "ops"},
    {"id": "ai_usage", "title": "AI Usage Guide", "path": "AI_USAGE_GUIDE.md", "type": "AI", "audience": "system"},
    {"id": "gsc_access", "title": "GSC Data Access", "path": ".ai/GSC_DATA_ACCESS.md", "type": "Data", "audience": "system"},
    {"id": "dashboard_workflows", "title": "Dashboard AI Workflows", "path": ".ai/DASHBOARD_WORKFLOWS.md", "type": "AI", "audience": "system"},
    {"id": "prompt_library", "title": "Prompt Library", "path": ".ai/PROMPT_LIBRARY.md", "type": "Prompt", "audience": "system"},
    {"id": "handoff", "title": "AI Handoff Log", "path": ".ai/HANDOFF_LOG.md", "type": "AI", "audience": "system"},
]


def json_response(handler: BaseHTTPRequestHandler, data: object, status: int = 200) -> None:
    payload = json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(payload)))
    handler.end_headers()
    handler.wfile.write(payload)


def text_response(handler: BaseHTTPRequestHandler, text: str, content_type: str = "text/plain; charset=utf-8", status: int = 200) -> None:
    payload = text.encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", content_type)
    handler.send_header("Content-Length", str(len(payload)))
    handler.end_headers()
    handler.wfile.write(payload)


def safe_project_path(relative_path: str) -> Path:
    path = (ROOT / relative_path).resolve()
    if not str(path).lower().startswith(str(ROOT.resolve()).lower()):
        raise ValueError("Path escapes project root.")
    return path


def load_env_masked() -> dict[str, object]:
    env_path = ROOT / ".env"
    values: dict[str, str] = {}
    if env_path.exists():
        for raw_line in env_path.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            if key.startswith(("GSC_", "GA4_", "PAGESPEED_", "CRUX_", "SITE_", "TARGET_", "BRAND_", "PRIMARY_", "SITEMAP_", "ROBOTS_")):
                values[key] = value
    masked: dict[str, object] = {}
    for key in [
        "GSC_READONLY_SCOPE",
        "GSC_OAUTH_CLIENT_ID",
        "GSC_OAUTH_CLIENT_SECRET",
        "GSC_OAUTH_REFRESH_TOKEN",
        "GSC_SITE_URL",
        "GSC_CACHE_DIR",
        "SITE_CANONICAL_HOST",
        "TARGET_COUNTRIES",
        "TARGET_LANGUAGES",
        "BRAND_KEYWORDS",
        "PRIMARY_CONVERSIONS",
        "SITEMAP_URL",
        "ROBOTS_URL",
        "GA4_PROPERTY_ID",
        "GA4_READONLY_SCOPE",
        "GA4_OAUTH_CLIENT_ID",
        "GA4_OAUTH_CLIENT_SECRET",
        "GA4_OAUTH_REFRESH_TOKEN",
        "GA4_CACHE_DIR",
        "PAGESPEED_API_KEY",
        "PAGESPEED_DEFAULT_STRATEGY",
        "PAGESPEED_DEFAULT_CATEGORIES",
        "PAGESPEED_CACHE_DIR",
        "CRUX_API_KEY",
        "CRUX_FORM_FACTOR",
        "CRUX_CACHE_DIR",
    ]:
        value = values.get(key, "")
        display = value
        if "SECRET" in key or "TOKEN" in key or "API_KEY" in key:
            display = mask_secret(value)
        masked[key] = {"configured": bool(value), "value": display}
    return masked


def mask_secret(value: str) -> str:
    if not value:
        return ""
    if len(value) <= 8:
        return "***"
    return value[:4] + "..." + value[-4:]


def load_env_values() -> dict[str, str]:
    values: dict[str, str] = {}
    env_path = ROOT / ".env"
    if not env_path.exists():
        return values
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def positive_int(value: str) -> int | None:
    try:
        parsed = int(float(value))
    except (TypeError, ValueError):
        return None
    return parsed if parsed > 0 else None


def gsc_exports() -> list[dict[str, object]]:
    if not RAW_GSC_DIR.exists():
        return []
    exports = []
    for path in sorted(RAW_GSC_DIR.glob("gsc_*.csv"), key=lambda item: item.stat().st_mtime, reverse=True):
        exports.append(
            {
                "name": path.name,
                "path": str(path.relative_to(ROOT)).replace("\\", "/"),
                "bytes": path.stat().st_size,
                "modified": dt.datetime.fromtimestamp(path.stat().st_mtime).isoformat(timespec="seconds"),
                "rows": max(count_lines(path) - 1, 0),
            }
        )
    return exports


def count_lines(path: Path) -> int:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return sum(1 for _ in handle)


def latest_csv(kind: str) -> Path | None:
    if not RAW_GSC_DIR.exists():
        return None
    files = list(RAW_GSC_DIR.glob(f"*_{kind}_*.csv"))
    if not files:
        return None
    return max(files, key=lambda item: item.stat().st_mtime)


def latest_json(directory: Path, prefix: str) -> Path | None:
    if not directory.exists():
        return None
    files = list(directory.glob(f"{prefix}*.json"))
    if not files:
        return None
    return max(files, key=lambda item: item.stat().st_mtime)


def raw_file_snapshot(directory: Path) -> set[Path]:
    if not directory.exists():
        return set()
    return {path.resolve() for path in directory.iterdir() if path.is_file() and path.suffix.lower() in {".csv", ".json"}}


def new_raw_files(directory: Path, before: set[Path]) -> list[Path]:
    after = raw_file_snapshot(directory)
    return sorted(after - before, key=lambda item: item.stat().st_mtime)


def directory_summary(directory: Path) -> dict[str, object]:
    files = []
    if directory.exists():
        files = [path for path in directory.iterdir() if path.is_file() and path.suffix.lower() in {".csv", ".json"}]
    latest = max(files, key=lambda item: item.stat().st_mtime) if files else None
    return {
        "path": str(directory.relative_to(ROOT)).replace("\\", "/"),
        "exists": directory.exists(),
        "files": len(files),
        "bytes": sum(path.stat().st_size for path in files),
        "latestFile": latest.name if latest else "",
        "latestModified": dt.datetime.fromtimestamp(latest.stat().st_mtime).isoformat(timespec="seconds") if latest else "",
    }


def directory_tree_summary(directory: Path) -> dict[str, object]:
    files = [path for path in directory.rglob("*") if path.is_file()] if directory.exists() else []
    latest = max(files, key=lambda item: item.stat().st_mtime) if files else None
    return {
        "path": str(directory.relative_to(ROOT)).replace("\\", "/"),
        "exists": directory.exists(),
        "files": len(files),
        "bytes": sum(path.stat().st_size for path in files),
        "latestModified": dt.datetime.fromtimestamp(latest.stat().st_mtime).isoformat(timespec="seconds") if latest else "",
    }


def log_level(line: str) -> str:
    lowered = line.lower()
    if any(token in lowered for token in ("traceback", "exception", " error", "failed", "failure")):
        return "error"
    if "warning" in lowered or " warn" in lowered:
        return "warning"
    return "info"


def log_file_summary(path: Path, tail_limit: int = 30) -> dict[str, object]:
    if not path.exists():
        return {
            "name": path.name,
            "exists": False,
            "bytes": 0,
            "modified": "",
            "lineCount": 0,
            "errorCount": 0,
            "warningCount": 0,
            "entries": [],
        }
    lines = [line.strip() for line in path.read_text(encoding="utf-8", errors="replace").splitlines() if line.strip()]
    inspected = lines[-500:]
    levels = [log_level(line) for line in inspected]
    entries = [
        {"level": log_level(line), "message": str(redact_secrets(line))[:320]}
        for line in lines[-tail_limit:]
    ]
    return {
        "name": path.name,
        "exists": True,
        "bytes": path.stat().st_size,
        "modified": dt.datetime.fromtimestamp(path.stat().st_mtime).isoformat(timespec="seconds"),
        "lineCount": len(lines),
        "errorCount": levels.count("error"),
        "warningCount": levels.count("warning"),
        "entries": entries,
    }


def quota_sources_with_limits(rows: list[dict[str, object]], env: dict[str, str]) -> list[dict[str, object]]:
    limit_keys = {
        "gsc": "GSC_DAILY_CALL_LIMIT",
        "ga4": "GA4_DAILY_CALL_LIMIT",
        "pagespeed": "PAGESPEED_DAILY_CALL_LIMIT",
        "crux": "CRUX_DAILY_CALL_LIMIT",
    }
    result = []
    for row in rows:
        source = str(row.get("source") or "")
        limit_key = limit_keys.get(source, "")
        limit = positive_int(env.get(limit_key, "")) if limit_key else None
        used = int(row.get("estimatedCallsToday") or 0)
        utilization = used / limit if limit else None
        if utilization is None:
            limit_status = "unconfigured"
        elif utilization >= 1:
            limit_status = "critical"
        elif utilization >= 0.8:
            limit_status = "warning"
        else:
            limit_status = "normal"
        result.append(
            {
                **row,
                "dailyLimit": limit,
                "limitConfigKey": limit_key,
                "utilization": utilization,
                "limitStatus": limit_status,
            }
        )
    return result


def operations_logs(recent_runs: list[dict[str, object]]) -> dict[str, object]:
    files = [log_file_summary(SERVER_OUT_LOG), log_file_summary(SERVER_ERR_LOG)]
    latest_by_source: dict[str, dict[str, object]] = {}
    for row in recent_runs:
        source = str(row.get("source") or "unknown")
        latest_by_source.setdefault(source, row)
    api_issues = []
    for source, row in latest_by_source.items():
        if row.get("status") == "ok":
            continue
        message = str(redact_secrets(str(row.get("error") or "API sync failed.")))[:320]
        expected_no_data = source == "crux" and ("404" in message or "no data" in message.lower())
        api_issues.append(
            {
                "level": "warning" if expected_no_data else "error",
                "source": source,
                "createdAt": str(row.get("created_at") or ""),
                "message": message,
            }
        )
    file_errors = sum(int(item["errorCount"]) for item in files)
    warnings = sum(int(item["warningCount"]) for item in files) + sum(1 for item in api_issues if item["level"] == "warning")
    api_errors = sum(1 for item in api_issues if item["level"] == "error")
    return {
        "status": "attention" if file_errors or api_issues else "healthy",
        "errorCount": file_errors + api_errors,
        "warningCount": warnings,
        "files": files,
        "apiIssues": api_issues,
    }


def storage_overview() -> dict[str, object]:
    env = load_env_values()
    cloud = cloud_status()
    raw_directories = {
        "gsc": directory_summary(RAW_GSC_DIR),
        "ga4": directory_summary(RAW_GA4_DIR),
        "pagespeed": directory_summary(RAW_PAGESPEED_DIR),
        "crux": directory_summary(RAW_CRUX_DIR),
    }
    recent_runs = recent_api_runs(50)
    quota_sources = quota_sources_with_limits(api_source_status(30), env)
    disk = shutil.disk_usage(ROOT)
    backup = directory_tree_summary(BACKUP_ROOT)
    sqlite_path = ROOT / "data" / "local" / "seo_dashboard.sqlite"
    sqlite_bytes = sqlite_path.stat().st_size if sqlite_path.exists() else 0
    raw_bytes = sum(int(item["bytes"]) for item in raw_directories.values())
    cloud_bytes = int(cloud.get("health", {}).get("databaseBytes") or 0)
    cloud_limit = positive_int(env.get("SUPABASE_DATABASE_LIMIT_BYTES", ""))
    return {
        "architecture": {
            "mode": "local_first_cloud_replica",
            "sourceOfTruth": "Local raw exports plus SQLite operational tables",
            "cloudRole": "Supabase Postgres replica and analysis database",
            "backupPolicy": "Create a local backup under data/backups/supabase_uploads before cloud upload",
        },
        "sqlite": {
            "path": str(sqlite_path.relative_to(ROOT)).replace("\\", "/"),
            "exists": sqlite_path.exists(),
            "bytes": sqlite_bytes,
        },
        "rawDirectories": raw_directories,
        "capacity": {
            "localDisk": {
                "totalBytes": disk.total,
                "usedBytes": disk.used,
                "freeBytes": disk.free,
                "utilization": disk.used / disk.total if disk.total else 0,
            },
            "sqlite": {"bytes": sqlite_bytes},
            "rawCache": {"bytes": raw_bytes},
            "backups": backup,
            "cloudDatabase": {
                "bytes": cloud_bytes or None,
                "limitBytes": cloud_limit,
                "utilization": cloud_bytes / cloud_limit if cloud_bytes and cloud_limit else None,
                "limitConfigKey": "SUPABASE_DATABASE_LIMIT_BYTES",
            },
        },
        "quota": {
            "summary": api_run_summary(7),
            "sources": quota_sources,
            "rules": {
                "gsc": "Refresh daily unless forced.",
                "ga4": "Refresh daily unless forced.",
                "pagespeed": "Refresh when a URL is new, stale after 7 days, changed, or forced.",
                "crux": "Refresh monthly or after meaningful traffic growth.",
            },
            "officialMonitoring": {
                "status": "reserved",
                "projectConfigured": bool(env.get("GOOGLE_CLOUD_PROJECT_ID")),
                "enabled": env.get("GOOGLE_CLOUD_MONITORING_ENABLED", "").lower() in {"1", "true", "yes"},
                "requiredConfig": ["GOOGLE_CLOUD_PROJECT_ID", "GOOGLE_CLOUD_MONITORING_ENABLED"],
                "message": "Official quota metrics require a future Google Cloud Monitoring connector.",
            },
        },
        "cloud": cloud,
        "logs": operations_logs(recent_runs),
        "recentRuns": recent_runs,
    }


def read_json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def clean_text(value: object) -> object:
    if isinstance(value, str):
        return value.replace("\u00a0", " ")
    if isinstance(value, dict):
        return {key: clean_text(item) for key, item in value.items()}
    if isinstance(value, list):
        return [clean_text(item) for item in value]
    return value


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def metric_float(row: dict[str, str], key: str) -> float:
    try:
        return float(row.get(key, "") or 0)
    except ValueError:
        return 0.0


def parse_date(value: str) -> dt.date | None:
    if not value:
        return None
    for fmt in ("%Y-%m-%d", "%Y%m%d"):
        try:
            return dt.datetime.strptime(value, fmt).date()
        except ValueError:
            continue
    return None


def normalize_ga4_date(value: str) -> str:
    parsed = parse_date(value)
    return parsed.isoformat() if parsed else value


def normalize_number(value: object) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def aggregate_metrics(rows: list[dict[str, str]]) -> dict[str, float]:
    clicks = sum(metric_float(row, "clicks") for row in rows)
    impressions = sum(metric_float(row, "impressions") for row in rows)
    return {
        "clicks": round(clicks, 4),
        "impressions": round(impressions, 4),
        "ctr": round(clicks / impressions, 6) if impressions else 0,
        "position": round(weighted_average(rows, "position", "impressions"), 4),
        "rows": len(rows),
    }


def aggregate_by(rows: list[dict[str, str]], key: str) -> list[dict[str, object]]:
    grouped: dict[str, list[dict[str, str]]] = {}
    for row in rows:
        label = row.get(key, "") or "(not set)"
        grouped.setdefault(label, []).append(row)
    items = []
    for label, group_rows in grouped.items():
        metrics = aggregate_metrics(group_rows)
        items.append(
            {
                "label": label,
                "clicks": metrics["clicks"],
                "impressions": metrics["impressions"],
                "ctr": metrics["ctr"],
                "position": metrics["position"],
                "rows": metrics["rows"],
                "reason": opportunity_reason(metrics["clicks"], metrics["impressions"], metrics["ctr"], metrics["position"]),
            }
        )
    return items


def sort_metric_items(items: list[dict[str, object]], sort_key: str = "clicks", descending: bool = True) -> list[dict[str, object]]:
    if sort_key == "position":
        descending = False
    return sorted(items, key=lambda item: normalize_number(item.get(sort_key)), reverse=descending)


def metric_delta(current: dict[str, float], previous: dict[str, float], total_click_delta: float = 0) -> dict[str, object]:
    result: dict[str, object] = {}
    for metric in ("clicks", "impressions", "ctr", "position"):
        now = normalize_number(current.get(metric))
        before = normalize_number(previous.get(metric))
        delta = now - before
        result[f"previous_{metric}"] = round(before, 6)
        result[f"delta_{metric}"] = round(delta, 6)
        result[f"change_{metric}"] = round(delta / before, 6) if before else None
    result["click_contribution"] = round(normalize_number(result["delta_clicks"]) / total_click_delta, 6) if total_click_delta else None
    return result


def parse_gsc_filters(params: dict[str, list[str]]) -> list[dict[str, object]]:
    raw = params.get("filters", [""])[0]
    if raw:
        try:
            filters = json.loads(raw)
            if isinstance(filters, list):
                return [item for item in filters if isinstance(item, dict)]
        except json.JSONDecodeError:
            pass
    result = []
    for field in ("query", "page"):
        value = (params.get(field, [""])[0] or "").strip()
        if value:
            result.append({"field": field, "operator": "contains", "value": value})
    return result


def filter_matches(row: dict[str, str], item: dict[str, object]) -> bool:
    field = str(item.get("field") or "")
    operator = str(item.get("operator") or "contains")
    value = str(item.get("value") or "")
    actual = str(row.get(field) or "")
    left, right = actual.casefold(), value.casefold()
    if field not in {"query", "page"} or operator not in {"equals", "not_equals", "contains", "not_contains", "starts_with", "regex", "list"}:
        return False
    if operator == "equals": return left == right
    if operator == "not_equals": return left != right
    if operator == "contains": return right in left
    if operator == "not_contains": return right not in left
    if operator == "starts_with": return left.startswith(right)
    if operator == "list": return left in {part.strip().casefold() for part in value.split(",") if part.strip()}
    try:
        return re.search(value, actual, re.IGNORECASE) is not None
    except re.error:
        return False


def date_window(value: str, available_end: dt.date, params: dict[str, list[str]]) -> tuple[dt.date, dt.date]:
    if value == "custom":
        start = parse_date(params.get("start", [""])[0]) or available_end
        end = parse_date(params.get("end", [""])[0]) or available_end
        return (min(start, end), max(start, end))
    if value == "mtd": return available_end.replace(day=1), available_end
    if value == "previous_month":
        end = available_end.replace(day=1) - dt.timedelta(days=1)
        return end.replace(day=1), end
    days = int(value) if value in {"7", "28", "90"} else 28
    return available_end - dt.timedelta(days=days - 1), available_end


def comparison_window(mode: str, start: dt.date, end: dt.date, params: dict[str, list[str]]) -> tuple[dt.date, dt.date] | None:
    span = (end - start).days + 1
    if mode == "none": return None
    if mode in {"previous", "weekday"}: return start - dt.timedelta(days=span), start - dt.timedelta(days=1)
    if mode == "year":
        try: return start.replace(year=start.year - 1), end.replace(year=end.year - 1)
        except ValueError: return start - dt.timedelta(days=365), end - dt.timedelta(days=365)
    if mode == "custom":
        a = parse_date(params.get("compareStart", [""])[0]); b = parse_date(params.get("compareEnd", [""])[0])
        return (min(a, b), max(a, b)) if a and b else None
    return None


def grain_label(date_value: str, grain: str) -> str:
    value = parse_date(date_value)
    if not value: return date_value
    if grain == "week": return f"{value.isocalendar().year}-W{value.isocalendar().week:02d}"
    if grain == "month": return value.strftime("%Y-%m")
    return value.isoformat()


def gsc_explorer(params: dict[str, list[str]]) -> dict[str, object]:
    date_query_page = latest_csv("date-query-page")
    rows = read_csv_rows(date_query_page) if date_query_page else []
    dates = sorted({parse_date(row.get("date", "")) for row in rows if parse_date(row.get("date", ""))})
    file_range = re.search(r"_(\d{4}-\d{2}-\d{2})_(\d{4}-\d{2}-\d{2})_", date_query_page.name) if date_query_page else None
    available_start = parse_date(file_range.group(1)) if file_range else (dates[0] if dates else dt.date.today())
    available_end = parse_date(file_range.group(2)) if file_range else (dates[-1] if dates else dt.date.today())
    preset = params.get("preset", ["28"])[0]
    start_date, end_date = date_window(preset, available_end, params)
    compare_mode = params.get("compare", ["previous"])[0]
    compare_dates = comparison_window(compare_mode, start_date, end_date, params)
    if not compare_dates or compare_mode == "none":
        comparison_status = "none"
    elif compare_dates[1] < available_start or compare_dates[0] > available_end:
        comparison_status = "unavailable"
    elif compare_dates[0] < available_start or compare_dates[1] > available_end:
        comparison_status = "partial"
    else:
        comparison_status = "complete"
    grain = params.get("grain", ["day"])[0] if params.get("grain", ["day"])[0] in {"day", "week", "month"} else "day"
    dimension = params.get("dimension", ["query"])[0]
    if dimension not in {"query", "page", "date"}: dimension = "query"
    filters = parse_gsc_filters(params)
    min_impressions = normalize_number(params.get("minImpressions", ["0"])[0] if params.get("minImpressions") else 0)
    sort_key = params.get("sort", ["clicks"])[0] or "clicks"
    limit = int(normalize_number(params.get("limit", ["50"])[0] if params.get("limit") else 50) or 50)

    scoped = [row for row in rows if all(filter_matches(row, item) for item in filters)]
    filtered, previous_rows = [], []
    for row in scoped:
        row_date = parse_date(row.get("date", ""))
        if row_date and start_date <= row_date <= end_date: filtered.append(row)
        if compare_dates and row_date and compare_dates[0] <= row_date <= compare_dates[1]: previous_rows.append(row)

    trend_rows = [{**row, "period": grain_label(row.get("date", ""), grain)} for row in filtered]
    by_date = aggregate_by(trend_rows, "period")
    by_date = sorted(by_date, key=lambda item: str(item["label"]))
    current_groups = {str(item["label"]): item for item in aggregate_by(filtered, dimension)}
    previous_groups = {str(item["label"]): item for item in aggregate_by(previous_rows, dimension)}
    total_click_delta = aggregate_metrics(filtered)["clicks"] - aggregate_metrics(previous_rows)["clicks"]
    comparison_rows = []
    for label in set(current_groups) | set(previous_groups):
        current = current_groups.get(label, {"label": label, "clicks": 0, "impressions": 0, "ctr": 0, "position": 0, "rows": 0})
        previous = previous_groups.get(label, {"clicks": 0, "impressions": 0, "ctr": 0, "position": 0})
        comparison_rows.append({**current, **metric_delta(current, previous, total_click_delta)})
    if comparison_status in {"unavailable", "none"}:
        for item in comparison_rows:
            for metric in ("clicks", "impressions", "ctr", "position"):
                item[f"previous_{metric}"] = None
                item[f"delta_{metric}"] = None
                item[f"change_{metric}"] = None
            item["click_contribution"] = None
    comparison_rows = [item for item in comparison_rows if normalize_number(item["impressions"]) >= min_impressions]
    raw_rows = [
        {
            "date": row.get("date", ""),
            "query": row.get("query", ""),
            "page": row.get("page", ""),
            "clicks": metric_float(row, "clicks"),
            "impressions": metric_float(row, "impressions"),
            "ctr": metric_float(row, "ctr"),
            "position": metric_float(row, "position"),
        }
        for row in filtered
        if metric_float(row, "impressions") >= min_impressions
    ]
    raw_rows = sort_metric_items(raw_rows, sort_key)[:limit]
    totals = aggregate_metrics(filtered); previous_totals = aggregate_metrics(previous_rows)
    totals.update(metric_delta(totals, previous_totals, total_click_delta))
    if comparison_status in {"unavailable", "none"}:
        for metric in ("clicks", "impressions", "ctr", "position"):
            totals[f"previous_{metric}"] = None
            totals[f"delta_{metric}"] = None
            totals[f"change_{metric}"] = None
        totals["click_contribution"] = None
    available_dimensions = {"query": "Available now", "page": "Available now", "date": "Available now", "country": "Requires new collection", "device": "Requires new collection", "searchAppearance": "Requires new collection"}

    return {
        "sourceFile": str(date_query_page.relative_to(ROOT)).replace("\\", "/") if date_query_page else None,
        "contractVersion": "gsc-phase1-v1",
        "totals": totals,
        "trend": by_date,
        "table": sort_metric_items(comparison_rows, sort_key)[:limit],
        "queries": sort_metric_items(aggregate_by(filtered, "query"), sort_key)[:limit],
        "pages": sort_metric_items(aggregate_by(filtered, "page"), sort_key)[:limit],
        "rows": raw_rows,
        "filters": {
            "start": start_date.isoformat(), "end": end_date.isoformat(), "preset": preset,
            "compare": compare_mode, "comparisonStatus": comparison_status, "compareStart": compare_dates[0].isoformat() if compare_dates else "", "compareEnd": compare_dates[1].isoformat() if compare_dates else "",
            "grain": grain, "dimension": dimension, "items": filters,
        },
        "metadata": {"source": "Google Search Console cached export", "property": "sc-domain:elecrest.energy", "timezone": "Pacific Time (GSC reporting)", "availableStart": available_start.isoformat(), "availableEnd": available_end.isoformat(), "latestCompleteDate": available_end.isoformat(), "rowLimit": limit, "availableDimensions": available_dimensions, "freshness": dt.datetime.fromtimestamp(date_query_page.stat().st_mtime).isoformat(timespec="seconds") if date_query_page else "", "limitations": ["Cached export contains date + query + page only.", "Comparison values are suppressed when the requested baseline is outside cached coverage; partial coverage is labeled partial.", "Anonymous queries and API row limits can make table totals differ from GSC chart totals.", "CTR is clicks / impressions; position is impression-weighted.", "Average position is aggregated and is not a live rank."]},
    }


def summarize_gsc() -> dict[str, object]:
    date_query_page = latest_csv("date-query-page")
    query_file = latest_csv("query")
    page_file = latest_csv("page")
    rows = read_csv_rows(date_query_page) if date_query_page else []
    query_rows = read_csv_rows(query_file) if query_file else []
    page_rows = read_csv_rows(page_file) if page_file else []

    total_clicks = sum(metric_float(row, "clicks") for row in rows)
    total_impressions = sum(metric_float(row, "impressions") for row in rows)
    weighted_position = weighted_average(rows, "position", "impressions")
    ctr = total_clicks / total_impressions if total_impressions else 0

    by_date: dict[str, dict[str, float]] = {}
    for row in rows:
        date = row.get("date", "")
        if not date:
            continue
        item = by_date.setdefault(date, {"clicks": 0.0, "impressions": 0.0, "position_sum": 0.0, "position_weight": 0.0})
        impressions = metric_float(row, "impressions")
        item["clicks"] += metric_float(row, "clicks")
        item["impressions"] += impressions
        item["position_sum"] += metric_float(row, "position") * impressions
        item["position_weight"] += impressions

    trend = []
    for date in sorted(by_date):
        item = by_date[date]
        impressions = item["impressions"]
        trend.append(
            {
                "date": date,
                "clicks": round(item["clicks"], 4),
                "impressions": round(impressions, 4),
                "ctr": round(item["clicks"] / impressions, 6) if impressions else 0,
                "position": round(item["position_sum"] / item["position_weight"], 4) if item["position_weight"] else 0,
            }
        )

    query_opportunities = sorted(
        [
            normalize_opportunity(row, "query")
            for row in query_rows
            if metric_float(row, "impressions") > 0
        ],
        key=lambda item: (item["clicks"], -item["impressions"], item["position"]),
    )
    page_opportunities = sorted(
        [
            normalize_opportunity(row, "page")
            for row in page_rows
            if metric_float(row, "impressions") > 0
        ],
        key=lambda item: (item["clicks"], -item["impressions"], item["position"]),
    )

    return {
        "sourceFiles": {
            "dateQueryPage": str(date_query_page.relative_to(ROOT)).replace("\\", "/") if date_query_page else None,
            "query": str(query_file.relative_to(ROOT)).replace("\\", "/") if query_file else None,
            "page": str(page_file.relative_to(ROOT)).replace("\\", "/") if page_file else None,
        },
        "totals": {
            "clicks": round(total_clicks, 4),
            "impressions": round(total_impressions, 4),
            "ctr": round(ctr, 6),
            "position": round(weighted_position, 4),
            "rows": len(rows),
        },
        "trend": trend,
        "topQueries": top_items(query_rows, "query"),
        "topPages": top_items(page_rows, "page"),
        "queryOpportunities": query_opportunities[:10],
        "pageOpportunities": page_opportunities[:10],
        "exports": gsc_exports()[:20],
    }


def summarize_ga4() -> dict[str, object]:
    latest = latest_json(RAW_GA4_DIR, "ga4_")
    last_run = latest_api_run("ga4")
    if not latest:
        return {
            "status": "error" if last_run and last_run.get("status") == "error" else "not_configured",
            "message": ga4_issue_message(last_run),
            "sourceFile": None,
            "latestRun": last_run,
            "totals": {},
            "rows": [],
        }
    data = read_json(latest)
    response = data.get("response", {})
    rows = response.get("rows", []) if isinstance(response, dict) else []
    dimension_headers = [item.get("name", "") for item in response.get("dimensionHeaders", [])]
    metric_headers = [item.get("name", "") for item in response.get("metricHeaders", [])]
    normalized = []
    totals: dict[str, float] = {}
    for row in rows:
        item: dict[str, object] = {}
        for index, header in enumerate(dimension_headers):
            item[header] = row.get("dimensionValues", [{}])[index].get("value", "") if index < len(row.get("dimensionValues", [])) else ""
        for index, header in enumerate(metric_headers):
            value = row.get("metricValues", [{}])[index].get("value", "0") if index < len(row.get("metricValues", [])) else "0"
            try:
                number: float | int = float(value)
                if number.is_integer():
                    number = int(number)
            except ValueError:
                number = 0
            item[header] = number
            totals[header] = totals.get(header, 0) + float(number)
        normalized.append(item)
    return {
        "status": "ok",
        "message": "GA4 data available.",
        "sourceFile": str(latest.relative_to(ROOT)).replace("\\", "/"),
        "latestRun": last_run,
        "totals": totals,
        "rows": normalized[:50],
    }


def latest_ga4_rows() -> tuple[Path | None, list[dict[str, object]]]:
    latest = latest_json(RAW_GA4_DIR, "ga4_")
    if not latest:
        return None, []
    data = read_json(latest)
    response = data.get("response", {})
    if not isinstance(response, dict):
        return latest, []
    dimension_headers = [item.get("name", "") for item in response.get("dimensionHeaders", [])]
    metric_headers = [item.get("name", "") for item in response.get("metricHeaders", [])]
    rows = []
    for row in response.get("rows", []):
        item: dict[str, object] = {}
        dimensions = row.get("dimensionValues", [])
        metrics = row.get("metricValues", [])
        for index, header in enumerate(dimension_headers):
            value = dimensions[index].get("value", "") if index < len(dimensions) else ""
            item[header] = normalize_ga4_date(value) if header == "date" else value
        for index, header in enumerate(metric_headers):
            value = metrics[index].get("value", "0") if index < len(metrics) else "0"
            item[header] = normalize_number(value)
        rows.append(item)
    return latest, rows


def ga4_analytics(params: dict[str, list[str]]) -> dict[str, object]:
    latest, rows = latest_ga4_rows()
    channel_filter = (params.get("channel", [""])[0] or "").strip().lower()
    if channel_filter:
        rows = [row for row in rows if channel_filter in str(row.get("sessionDefaultChannelGroup", "")).lower()]

    totals: dict[str, float] = {"sessions": 0, "totalUsers": 0, "activeUsers": 0, "screenPageViews": 0, "engagedSessions": 0}
    by_date: dict[str, dict[str, float]] = {}
    by_channel: dict[str, dict[str, float]] = {}
    for row in rows:
        date = str(row.get("date", ""))
        channel = str(row.get("sessionDefaultChannelGroup", "(not set)") or "(not set)")
        date_item = by_date.setdefault(date, dict(totals))
        channel_item = by_channel.setdefault(channel, dict(totals))
        for metric in totals:
            value = normalize_number(row.get(metric))
            totals[metric] += value
            date_item[metric] += value
            channel_item[metric] += value

    trend = []
    for date in sorted(by_date):
        item = by_date[date]
        sessions = item["sessions"]
        trend.append(
            {
                "date": date,
                **{metric: round(value, 4) for metric, value in item.items()},
                "engagementRate": round(item["engagedSessions"] / sessions, 6) if sessions else 0,
                "viewsPerSession": round(item["screenPageViews"] / sessions, 4) if sessions else 0,
            }
        )
    channels = []
    for channel, item in by_channel.items():
        sessions = item["sessions"]
        channels.append(
            {
                "channel": channel,
                **{metric: round(value, 4) for metric, value in item.items()},
                "engagementRate": round(item["engagedSessions"] / sessions, 6) if sessions else 0,
                "viewsPerSession": round(item["screenPageViews"] / sessions, 4) if sessions else 0,
            }
        )
    channels = sorted(channels, key=lambda item: item["sessions"], reverse=True)
    all_channels = sorted({str(row.get("sessionDefaultChannelGroup", "")) for row in latest_ga4_rows()[1] if row.get("sessionDefaultChannelGroup")})
    sessions = totals["sessions"]
    totals["engagementRate"] = round(totals["engagedSessions"] / sessions, 6) if sessions else 0
    totals["viewsPerSession"] = round(totals["screenPageViews"] / sessions, 4) if sessions else 0

    return {
        "status": "ok" if latest else "not_configured",
        "sourceFile": str(latest.relative_to(ROOT)).replace("\\", "/") if latest else None,
        "totals": {key: round(value, 4) for key, value in totals.items()},
        "trend": trend,
        "channels": channels,
        "rows": rows[:200],
        "filters": {"channels": all_channels, "channel": channel_filter},
    }


def ga4_issue_message(last_run: dict[str, object] | None) -> str:
    if not last_run:
        return "GA4 has not been synced yet."
    error = str(last_run.get("error") or "")
    if "PERMISSION_DENIED" in error or "403" in error:
        return "GA4 token works, but this account cannot read the configured GA4 property. Check GA4_PROPERTY_ID and account permission."
    return error or "GA4 data unavailable."


def summarize_pagespeed() -> dict[str, object]:
    latest = latest_json(RAW_PAGESPEED_DIR, "pagespeed_")
    last_run = latest_api_run("pagespeed")
    if not latest:
        return {"status": "not_configured", "message": "PageSpeed has not been synced yet.", "sourceFile": None, "latestRun": last_run, "summary": {}}
    data = read_json(latest)
    summary = data.get("summary", {})
    summary = clean_text(summary)
    return {
        "status": "ok",
        "message": "PageSpeed data available.",
        "sourceFile": str(latest.relative_to(ROOT)).replace("\\", "/"),
        "latestRun": last_run,
        "summary": summary,
    }


def pagespeed_strategy_from_name(path: Path) -> str:
    match = re.search(r"_(mobile|desktop)_\d{8}_\d{6}\.json$", path.name)
    return match.group(1) if match else ""


def parse_pagespeed_run(path: Path) -> dict[str, object] | None:
    try:
        data = read_json(path)
    except (OSError, json.JSONDecodeError):
        return None
    summary = clean_text(data.get("summary", {}))
    if not isinstance(summary, dict):
        return None
    scores = summary.get("scores", {}) if isinstance(summary.get("scores"), dict) else {}
    metrics = summary.get("coreMetrics", {}) if isinstance(summary.get("coreMetrics"), dict) else {}
    fetched_at = str(summary.get("fetchTime") or "")
    fetched_date = parse_date(fetched_at[:10])
    age_days = (dt.date.today() - fetched_date).days if fetched_date else None
    return {
        "url": summary.get("requestedUrl", ""),
        "finalUrl": summary.get("finalUrl", ""),
        "strategy": pagespeed_strategy_from_name(path),
        "fetchedAt": fetched_at,
        "ageDays": age_days,
        "isStale": age_days is None or age_days > 7,
        "staleReason": "Older than 7 days or unknown fetch time." if age_days is None or age_days > 7 else "",
        "scores": {
            "performance": normalize_number(scores.get("performance")),
            "accessibility": normalize_number(scores.get("accessibility")),
            "bestPractices": normalize_number(scores.get("best-practices")),
            "seo": normalize_number(scores.get("seo")),
        },
        "metrics": {
            "lcp": metrics.get("largest-contentful-paint", ""),
            "tbt": metrics.get("total-blocking-time", ""),
            "cls": metrics.get("cumulative-layout-shift", ""),
            "speedIndex": metrics.get("speed-index", ""),
        },
        "rawPath": str(path.relative_to(ROOT)).replace("\\", "/"),
        "modified": dt.datetime.fromtimestamp(path.stat().st_mtime).isoformat(timespec="seconds"),
    }


def gsc_priority_pages() -> list[dict[str, object]]:
    page_file = latest_csv("page")
    rows = read_csv_rows(page_file) if page_file else []
    pages = sort_metric_items(aggregate_by(rows, "page"), "impressions")[:50]
    return pages


def pagespeed_history(params: dict[str, list[str]]) -> dict[str, object]:
    url_filter = (params.get("url", [""])[0] or "").strip()
    strategy_filter = (params.get("strategy", [""])[0] or "").strip().lower()
    runs = []
    if RAW_PAGESPEED_DIR.exists():
        for path in sorted(RAW_PAGESPEED_DIR.glob("pagespeed_*.json"), key=lambda item: item.stat().st_mtime, reverse=True):
            run = parse_pagespeed_run(path)
            if not run:
                continue
            if url_filter and run.get("url") != url_filter:
                continue
            if strategy_filter and run.get("strategy") != strategy_filter:
                continue
            runs.append(run)

    latest_by_url: dict[str, dict[str, object]] = {}
    for run in runs:
        key = f"{run.get('url')}|{run.get('strategy')}"
        if key not in latest_by_url:
            latest_by_url[key] = run
    priority_pages = gsc_priority_pages()
    tested_urls = sorted({str(run.get("url")) for run in runs if run.get("url")})
    page_options = []
    for page in priority_pages:
        url = str(page.get("label") or "")
        latest_run = next((run for run in runs if run.get("url") == url), None)
        page_options.append(
            {
                "url": url,
                "clicks": page.get("clicks", 0),
                "impressions": page.get("impressions", 0),
                "tested": bool(latest_run),
                "latestFetchedAt": latest_run.get("fetchedAt", "") if latest_run else "",
                "isStale": latest_run.get("isStale", True) if latest_run else True,
            }
        )
    for url in tested_urls:
        if not any(item["url"] == url for item in page_options):
            page_options.append({"url": url, "clicks": 0, "impressions": 0, "tested": True, "latestFetchedAt": "", "isStale": False})

    return {
        "status": "ok" if runs else "not_configured",
        "runs": runs[:200],
        "latest": list(latest_by_url.values())[:50],
        "pages": page_options[:100],
        "sqliteRuns": recent_pagespeed_runs(30, url_filter),
    }


def summarize_crux() -> dict[str, object]:
    latest = latest_json(RAW_CRUX_DIR, "crux_")
    last_run = latest_api_run("crux")
    if not latest:
        message = "CrUX data not found for this origin/page. This usually means the site has insufficient real-user traffic in the CrUX dataset."
        if last_run and last_run.get("error"):
            message = message + " Latest API response: " + str(last_run.get("error"))[:240]
        return {"status": "no_data", "message": message, "sourceFile": None, "latestRun": last_run, "summary": {}}
    data = read_json(latest)
    summary = data.get("summary", {})
    return {
        "status": "ok",
        "message": "CrUX data available.",
        "sourceFile": str(latest.relative_to(ROOT)).replace("\\", "/"),
        "latestRun": last_run,
        "summary": summary,
    }


def weighted_average(rows: list[dict[str, str]], value_key: str, weight_key: str) -> float:
    total = 0.0
    weight_total = 0.0
    for row in rows:
        weight = metric_float(row, weight_key)
        total += metric_float(row, value_key) * weight
        weight_total += weight
    return total / weight_total if weight_total else 0.0


def normalize_opportunity(row: dict[str, str], label_key: str) -> dict[str, object]:
    clicks = metric_float(row, "clicks")
    impressions = metric_float(row, "impressions")
    ctr = metric_float(row, "ctr")
    position = metric_float(row, "position")
    return {
        "label": row.get(label_key, ""),
        "clicks": clicks,
        "impressions": impressions,
        "ctr": ctr,
        "position": position,
        "reason": opportunity_reason(clicks, impressions, ctr, position),
    }


def opportunity_reason(clicks: float, impressions: float, ctr: float, position: float) -> str:
    if impressions >= 10 and clicks == 0:
        return "Has impressions but no clicks"
    if position > 3 and position <= 20:
        return "Ranking within optimization range"
    if ctr < 0.05 and impressions > 0:
        return "Low CTR"
    return "Monitor"


def top_items(rows: list[dict[str, str]], label_key: str) -> list[dict[str, object]]:
    items = [normalize_opportunity(row, label_key) for row in rows]
    return sorted(items, key=lambda item: (-item["clicks"], -item["impressions"]))[:10]


def run_gsc_sync() -> dict[str, object]:
    commands = [
        [sys.executable, "tools/gsc_cli.py", "performance", "--dimensions", "date", "query", "page", "--save", "--quiet"],
        [sys.executable, "tools/gsc_cli.py", "performance", "--dimensions", "query", "--save", "--quiet"],
        [sys.executable, "tools/gsc_cli.py", "performance", "--dimensions", "page", "--save", "--quiet"],
    ]
    before_files = raw_file_snapshot(RAW_GSC_DIR)
    results = []
    for command in commands:
        completed = subprocess.run(
            command,
            cwd=str(ROOT),
            text=True,
            capture_output=True,
            timeout=120,
            check=False,
        )
        results.append(
            {
                "command": " ".join(command[1:]),
                "returnCode": completed.returncode,
                "stdout": completed.stdout.strip(),
                "stderr": redact_secrets(completed.stderr.strip()),
            }
        )
        if completed.returncode != 0:
            break
    ok = all(item["returnCode"] == 0 for item in results)
    exports = gsc_exports()[:10]
    run_summary = {"exports": len(exports), "latest": exports[0]["path"] if exports else ""}
    run_id = record_api_run(
        source="gsc",
        status="ok" if ok else "error",
        command="; ".join(item["command"] for item in results),
        summary=run_summary,
        raw_path=exports[0]["path"] if exports else "",
        error="" if ok else "\n".join(item["stderr"] for item in results if item["stderr"])[:2000],
    )
    cloud_sync = auto_upload_files(new_raw_files(RAW_GSC_DIR, before_files), "gsc_sync") if ok and is_supabase_configured() else {"ok": False, "skipped": True}
    run_summary["cloudSync"] = cloud_sync
    update_api_run_summary(run_id, run_summary)
    return {"ok": ok, "results": results, "exports": exports, "cloudSync": cloud_sync}


def run_api_command(source: str, command: list[str], timeout: int = 120) -> dict[str, object]:
    completed = subprocess.run(
        command,
        cwd=str(ROOT),
        text=True,
        capture_output=True,
        timeout=timeout,
        check=False,
        encoding="utf-8",
        errors="replace",
    )
    stdout = completed.stdout.strip()
    stderr = redact_api_secrets(completed.stderr.strip())
    combined = "\n".join(part for part in [stdout, stderr] if part)
    saved_path = extract_saved_path(combined)
    saved_file = resolve_saved_path(saved_path) if saved_path else None
    status = "ok" if completed.returncode == 0 else "error"
    summary = {}
    if saved_file:
        try:
            raw = read_json(saved_file)
            summary = raw.get("summary", {}) if isinstance(raw, dict) else {}
        except Exception:
            summary = {}
    if not isinstance(summary, dict):
        summary = {}
    run_id = record_api_run(
        source=source,
        status=status,
        command=" ".join(command[1:]),
        summary=summary,
        raw_path=str(saved_file.relative_to(ROOT)).replace("\\", "/") if saved_file else "",
        error="" if completed.returncode == 0 else combined[:2000],
    )
    if source == "pagespeed" and completed.returncode == 0 and isinstance(summary, dict):
        strategy = ""
        if "--strategy" in command:
            index = command.index("--strategy")
            strategy = command[index + 1] if index + 1 < len(command) else ""
        strategy = strategy or pagespeed_strategy_from_name(saved_file) if saved_file else strategy
        record_pagespeed_run(clean_text(summary), str(saved_file.relative_to(ROOT)).replace("\\", "/") if saved_file else "", strategy)
    cloud_sync = {"ok": False, "skipped": True}
    if completed.returncode == 0 and saved_file and is_supabase_configured():
        cloud_sync = auto_upload_files([saved_file], f"{source}_sync")
    summary["cloudSync"] = cloud_sync
    update_api_run_summary(run_id, summary)
    return {
        "source": source,
        "returnCode": completed.returncode,
        "stdout": stdout,
        "stderr": stderr,
        "savedPath": str(saved_file) if saved_file else "",
        "ok": completed.returncode == 0,
        "cloudSync": cloud_sync,
    }


def extract_saved_path(text: str) -> str:
    for line in text.splitlines():
        if line.startswith("Saved: "):
            return line.replace("Saved: ", "", 1).strip()
    return ""


def resolve_saved_path(saved_path: str) -> Path:
    path = Path(saved_path)
    if not path.is_absolute():
        path = ROOT / path
    path = path.resolve()
    if not str(path).lower().startswith(str(ROOT.resolve()).lower()):
        raise ValueError("Saved path escapes project root.")
    return path


def redact_api_secrets(text: str) -> str:
    if not text:
        return text
    parsed = parse.urlparse(text)
    if parsed.query:
        return text.replace(parsed.query, parse.urlencode([(k, "REDACTED" if k == "key" else v) for k, v in parse.parse_qsl(parsed.query)]))
    return text


def run_ga4_sync() -> dict[str, object]:
    result = run_api_command(
        "ga4",
        [
            sys.executable,
            "tools/ga4_cli.py",
            "report",
            "--dimensions",
            "date",
            "sessionDefaultChannelGroup",
            "--metrics",
            "sessions",
            "totalUsers",
            "activeUsers",
            "screenPageViews",
            "engagedSessions",
            "--limit",
            "1000",
            "--save",
            "--quiet",
        ],
        timeout=60,
    )
    return {"ok": result["ok"], "result": result, "summary": summarize_ga4()}


def run_pagespeed_sync(url: str = "", strategy: str = "") -> dict[str, object]:
    command = [sys.executable, "tools/pagespeed_cli.py", "run", "--summary", "--save"]
    if url:
        command.extend(["--url", url])
    if strategy:
        command.extend(["--strategy", strategy])
    result = run_api_command("pagespeed", command, timeout=180)
    return {"ok": result["ok"], "result": result, "summary": summarize_pagespeed(), "history": pagespeed_history({})}


def run_crux_sync() -> dict[str, object]:
    result = run_api_command("crux", [sys.executable, "tools/crux_cli.py", "query", "--form-factor", "ALL", "--summary", "--save"], timeout=60)
    return {"ok": result["ok"], "result": result, "summary": summarize_crux()}


def redact_secrets(text: str) -> str:
    if not text:
        return text
    sanitized = re.sub(r"(?i)(key|token|secret|password)=([^&\s]+)", r"\1=REDACTED", text)
    sanitized = re.sub(r"(?i)Bearer\s+[A-Za-z0-9._~-]+", "Bearer REDACTED", sanitized)
    for key, value in load_env_values().items():
        sensitive = any(token in key.upper() for token in ("SECRET", "TOKEN", "API_KEY", "PASSWORD"))
        sensitive = sensitive or (key.upper().startswith("SUPABASE_") and key.upper().endswith("_URL"))
        if sensitive and value and len(value) >= 6:
            sanitized = sanitized.replace(value, "REDACTED")
    return sanitized


def docs_index() -> list[dict[str, object]]:
    items = []
    for doc in DOCS:
        path = safe_project_path(doc["path"])
        items.append(
            {
                **doc,
                "exists": path.exists(),
                "modified": dt.datetime.fromtimestamp(path.stat().st_mtime).isoformat(timespec="seconds") if path.exists() else None,
                "bytes": path.stat().st_size if path.exists() else 0,
            }
        )
    return items


def read_doc(doc_id: str) -> dict[str, object]:
    matches = [doc for doc in DOCS if doc["id"] == doc_id]
    if not matches:
        raise ValueError("Unknown document id.")
    doc = matches[0]
    path = safe_project_path(doc["path"])
    content = path.read_text(encoding="utf-8") if path.exists() else ""
    return {**doc, "content": content, "exists": path.exists()}


def generate_ai_task(payload: dict[str, object]) -> dict[str, object]:
    task_type = str(payload.get("taskType") or "gsc_baseline_analysis")
    title = str(payload.get("title") or task_type.replace("_", " ").title())
    context = str(payload.get("context") or "")
    timestamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    AI_TASK_DIR.mkdir(parents=True, exist_ok=True)
    path = AI_TASK_DIR / f"{timestamp}_{task_type}.md"
    prompt = ai_prompt(task_type, title, context)
    path.write_text(prompt, encoding="utf-8")
    return {"path": str(path.relative_to(ROOT)).replace("\\", "/"), "content": prompt}


def ai_prompt(task_type: str, title: str, context: str) -> str:
    source = summarize_gsc().get("sourceFiles", {})
    return f"""# AI Task: {title}

## Required Reading

- `PROJECT_STATUS.md`
- `.ai/AI_OPERATING_MANUAL.md`
- `.ai/GSC_DATA_ACCESS.md`
- `05_reporting/monthly_report_template.md`
- `01_keyword_research/keyword_inventory.csv`
- `02_content/content_refresh_log.csv`

## Data Sources

- Latest date/query/page export: `{source.get("dateQueryPage")}`
- Latest query export: `{source.get("query")}`
- Latest page export: `{source.get("page")}`

## Task Type

{task_type}

## User Context

{context or "No extra context provided."}

## Instructions

Analyze the latest GSC data and update the relevant project files. Do not invent facts. Separate verified GSC data from assumptions. Add next actions to `backlog/seo_backlog.csv` if needed. Update `PROJECT_STATUS.md`, `CHANGELOG.md`, and `.ai/HANDOFF_LOG.md` after meaningful changes.
"""


class DashboardHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        parsed = parse.urlparse(self.path)
        path = parsed.path
        params = parse.parse_qs(parsed.query)
        try:
            if path == "/api/health":
                json_response(self, {"ok": True, "root": str(ROOT), "time": dt.datetime.now().isoformat(timespec="seconds")})
            elif path == "/api/status":
                json_response(self, {"env": load_env_masked(), "exports": gsc_exports()[:10], "docs": docs_index()})
            elif path == "/api/gsc/summary":
                json_response(self, summarize_gsc())
            elif path == "/api/gsc/explorer":
                json_response(self, gsc_explorer(params))
            elif path == "/api/ga4/summary":
                json_response(self, summarize_ga4())
            elif path == "/api/ga4/analytics":
                json_response(self, ga4_analytics(params))
            elif path == "/api/pagespeed/summary":
                json_response(self, summarize_pagespeed())
            elif path == "/api/pagespeed/history":
                json_response(self, pagespeed_history(params))
            elif path == "/api/crux/summary":
                json_response(self, summarize_crux())
            elif path == "/api/storage/overview":
                json_response(self, storage_overview())
            elif path == "/api/storage/runs":
                json_response(self, recent_api_runs(30))
            elif path == "/api/docs":
                json_response(self, docs_index())
            elif path == "/api/doc":
                doc_id = params.get("id", [""])[0]
                json_response(self, read_doc(doc_id))
            elif path.startswith("/api/file"):
                relative = params.get("path", [""])[0]
                file_path = safe_project_path(relative)
                if not file_path.exists():
                    json_response(self, {"error": "File not found."}, status=404)
                else:
                    text_response(self, file_path.read_text(encoding="utf-8"), "text/plain; charset=utf-8")
            else:
                self.serve_static(path)
        except Exception as exc:  # noqa: BLE001
            json_response(self, {"error": str(exc)}, status=500)

    def do_POST(self) -> None:
        parsed = parse.urlparse(self.path)
        try:
            length = int(self.headers.get("Content-Length", "0") or "0")
            body = self.rfile.read(length).decode("utf-8") if length else "{}"
            payload = json.loads(body or "{}")
            if parsed.path == "/api/gsc/sync":
                json_response(self, run_gsc_sync())
            elif parsed.path == "/api/ga4/sync":
                json_response(self, run_ga4_sync())
            elif parsed.path == "/api/pagespeed/sync":
                json_response(self, run_pagespeed_sync(str(payload.get("url") or ""), str(payload.get("strategy") or "")))
            elif parsed.path == "/api/crux/sync":
                json_response(self, run_crux_sync())
            elif parsed.path == "/api/ai/task":
                json_response(self, generate_ai_task(payload))
            else:
                json_response(self, {"error": "Unknown endpoint."}, status=404)
        except Exception as exc:  # noqa: BLE001
            json_response(self, {"error": str(exc)}, status=500)

    def serve_static(self, path: str) -> None:
        if path == "/":
            path = "/index.html"
        file_path = (APP_DIR / path.lstrip("/")).resolve()
        if not str(file_path).lower().startswith(str(APP_DIR.resolve()).lower()) or not file_path.exists():
            json_response(self, {"error": "Not found."}, status=404)
            return
        content_type = mimetypes.guess_type(str(file_path))[0] or "application/octet-stream"
        data = file_path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, format: str, *args: object) -> None:
        print(f"[dashboard] {self.address_string()} - {format % args}")


def main() -> None:
    port = 8766
    if len(sys.argv) > 1:
        port = int(sys.argv[1])
    server = ThreadingHTTPServer(("127.0.0.1", port), DashboardHandler)
    print(f"SEO dashboard running at http://127.0.0.1:{port}")
    print("Press Ctrl+C to stop.")
    server.serve_forever()


if __name__ == "__main__":
    main()
