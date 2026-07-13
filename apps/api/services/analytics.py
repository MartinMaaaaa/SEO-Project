from __future__ import annotations

import csv
import datetime as dt
import json
from pathlib import Path
import re
import subprocess
import sys
from typing import Any

from apps.api.core.config import ROOT, load_env
from apps.api.db.cloud_sync import auto_upload_files, is_supabase_configured
from apps.api.db.local_store import latest_api_run, recent_api_runs, recent_pagespeed_runs, record_api_run, record_pagespeed_run, update_api_run_summary

RAW = {name: ROOT / "data" / name / "raw" for name in ("gsc", "ga4", "pagespeed", "crux")}
TASK_DIR = ROOT / ".ai" / "runtime_tasks"


def _latest(directory: Path, pattern: str) -> Path | None:
    files = list(directory.glob(pattern)) if directory.exists() else []
    return max(files, key=lambda item: item.stat().st_mtime) if files else None


def _latest_gsc(kind: str) -> Path | None:
    return _latest(RAW["gsc"], f"*_{kind}_*.csv")


def _csv(path: Path | None) -> list[dict[str, str]]:
    if not path:
        return []
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _json(path: Path | None) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path else {}


def _number(value: Any) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def _date(value: str) -> dt.date | None:
    for fmt in ("%Y-%m-%d", "%Y%m%d"):
        try:
            return dt.datetime.strptime(value, fmt).date()
        except ValueError:
            pass
    return None


def _relative(path: Path | None) -> str | None:
    return str(path.relative_to(ROOT)).replace("\\", "/") if path else None


def _metrics(rows: list[dict[str, str]]) -> dict[str, float]:
    clicks = sum(_number(row.get("clicks")) for row in rows)
    impressions = sum(_number(row.get("impressions")) for row in rows)
    weighted = sum(_number(row.get("position")) * _number(row.get("impressions")) for row in rows)
    return {"clicks": round(clicks, 4), "impressions": round(impressions, 4), "ctr": round(clicks / impressions, 6) if impressions else 0, "position": round(weighted / impressions, 4) if impressions else 0, "rows": len(rows)}


def _aggregate(rows: list[dict[str, str]], field: str) -> list[dict[str, Any]]:
    groups: dict[str, list[dict[str, str]]] = {}
    for row in rows:
        groups.setdefault(row.get(field) or "(not set)", []).append(row)
    return [{"label": label, **_metrics(group)} for label, group in groups.items()]


def _match(row: dict[str, str], item: dict[str, Any]) -> bool:
    field, operator, value = str(item.get("field", "")), str(item.get("operator", "contains")), str(item.get("value", ""))
    if field not in {"query", "page"}:
        return False
    actual, expected = str(row.get(field, "")), value
    left, right = actual.casefold(), expected.casefold()
    if operator == "equals": return left == right
    if operator == "not_equals": return left != right
    if operator == "contains": return right in left
    if operator == "not_contains": return right not in left
    if operator == "starts_with": return left.startswith(right)
    if operator == "list": return left in {part.strip().casefold() for part in expected.split(",") if part.strip()}
    if operator == "regex":
        try: return re.search(expected, actual, re.IGNORECASE) is not None
        except re.error: return False
    return False


def _delta(current: dict[str, float], previous: dict[str, float], total_click_delta: float) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for metric in ("clicks", "impressions", "ctr", "position"):
        now, before = _number(current.get(metric)), _number(previous.get(metric))
        delta = now - before
        result[f"previous_{metric}"] = round(before, 6)
        result[f"delta_{metric}"] = round(delta, 6)
        result[f"change_{metric}"] = round(delta / before, 6) if before else None
    result["click_contribution"] = round(_number(result["delta_clicks"]) / total_click_delta, 6) if total_click_delta else None
    return result


def gsc_explorer(params: dict[str, list[str]]) -> dict[str, Any]:
    source = _latest_gsc("date-query-page")
    rows = _csv(source)
    dated = [(row, _date(row.get("date", ""))) for row in rows]
    dated = [(row, day) for row, day in dated if day]
    if not dated:
        return {"status": "no_data", "totals": _metrics([]), "trend": [], "tables": {"query": [], "page": [], "date": []}, "metadata": {"limitations": ["No cached date + query + page export is available."]}}
    coverage_start, coverage_end = min(day for _, day in dated), max(day for _, day in dated)
    preset = params.get("preset", ["custom" if params.get("start", [""])[0] else "28"])[0]
    if preset == "custom":
        start = _date(params.get("start", [""])[0]) or coverage_start
        end = _date(params.get("end", [""])[0]) or coverage_end
    else:
        days = int(preset) if preset in {"7", "28", "90"} else 28
        end, start = coverage_end, coverage_end - dt.timedelta(days=days - 1)
    if start > end: start, end = end, start
    filters: list[dict[str, Any]] = []
    raw_filters = params.get("filters", [""])[0]
    if raw_filters:
        try: filters = [item for item in json.loads(raw_filters) if isinstance(item, dict)]
        except (json.JSONDecodeError, TypeError): filters = []
    for field in ("query", "page"):
        value = params.get(field, [""])[0].strip()
        if value: filters.append({"field": field, "operator": "contains", "value": value})
    scoped = [row for row, day in dated if start <= day <= end and all(_match(row, item) for item in filters)]
    comparison_mode = params.get("comparison", ["previous_period"])[0]
    previous_rows: list[dict[str, str]] = []
    comparison_status = "none"
    previous_range = None
    if comparison_mode != "none":
        span = (end - start).days + 1
        previous_end, previous_start = start - dt.timedelta(days=1), start - dt.timedelta(days=span)
        previous_range = {"start": previous_start.isoformat(), "end": previous_end.isoformat()}
        if previous_start >= coverage_start and previous_end <= coverage_end:
            comparison_status = "complete"
            previous_rows = [row for row, day in dated if previous_start <= day <= previous_end and all(_match(row, item) for item in filters)]
        elif previous_end >= coverage_start:
            comparison_status = "partial"
        else:
            comparison_status = "unavailable"
    totals = _metrics(scoped)
    previous_totals = _metrics(previous_rows) if comparison_status == "complete" else None
    total_click_delta = totals["clicks"] - (previous_totals or {}).get("clicks", 0) if previous_totals else 0
    grain = params.get("grain", ["day"])[0]
    def grain_label(value: str) -> str:
        day = _date(value)
        if not day: return value
        if grain == "week":
            year, week, _ = day.isocalendar(); return f"{year}-W{week:02d}"
        if grain == "month": return day.strftime("%Y-%m")
        return day.isoformat()
    trend_rows = [{**row, "grain": grain_label(row.get("date", ""))} for row in scoped]
    trend = sorted(_aggregate(trend_rows, "grain"), key=lambda item: item["label"])
    limit = max(1, min(int(float(params.get("limit", ["50"])[0] or 50)), 200))
    sort_key = params.get("sort", ["clicks"])[0]
    tables = {}
    for field in ("query", "page", "date"):
        current = _aggregate(scoped, field)
        previous = {item["label"]: item for item in _aggregate(previous_rows, field)} if previous_totals else {}
        combined = [{**item, **(_delta(item, previous.get(item["label"], {}), total_click_delta) if previous_totals else {})} for item in current]
        tables[field] = sorted(combined, key=lambda item: _number(item.get(sort_key)), reverse=sort_key != "position")[:limit]
    return {"status": "ok", "totals": totals, "previousTotals": previous_totals, "deltas": _delta(totals, previous_totals, total_click_delta) if previous_totals else None, "trend": trend, "tables": tables, "comparison": {"mode": comparison_mode, "status": comparison_status, "range": previous_range}, "scope": {"range": {"start": start.isoformat(), "end": end.isoformat()}, "filters": filters, "grain": grain, "rowLimit": limit}, "metadata": {"source": "Google Search Console cached export", "property": load_env().get("GSC_SITE_URL", "Unknown"), "sourceFile": _relative(source), "timezone": "Pacific Time (GSC reporting)", "cacheCoverage": {"start": coverage_start.isoformat(), "end": coverage_end.isoformat()}, "freshness": dt.datetime.fromtimestamp(source.stat().st_mtime).isoformat(timespec="seconds"), "availableDimensions": {"date": True, "query": True, "page": True, "country": False, "device": False, "searchAppearance": False}, "limitations": ["Cached export contains date + query + page only.", "Comparison values are suppressed when baseline coverage is unavailable.", "Anonymous queries and API row limits can make table totals differ from GSC chart totals.", "CTR is recomputed; position is impression-weighted."]}}


def ga4_analytics(params: dict[str, list[str]]) -> dict[str, Any]:
    source = _latest(RAW["ga4"], "ga4_*.json")
    data = _json(source)
    response = data.get("response", {}) if isinstance(data, dict) else {}
    dimensions = [item.get("name", "") for item in response.get("dimensionHeaders", [])]
    metrics = [item.get("name", "") for item in response.get("metricHeaders", [])]
    rows = []
    for row in response.get("rows", []):
        item: dict[str, Any] = {}
        for index, name in enumerate(dimensions):
            value = row.get("dimensionValues", [])[index].get("value", "") if index < len(row.get("dimensionValues", [])) else ""
            item[name] = (_date(value).isoformat() if name == "date" and _date(value) else value)
        for index, name in enumerate(metrics):
            value = row.get("metricValues", [])[index].get("value", 0) if index < len(row.get("metricValues", [])) else 0
            item[name] = _number(value)
        rows.append(item)
    channel_filter = params.get("channel", [""])[0].strip().casefold()
    all_channels = sorted({str(row.get("sessionDefaultChannelGroup", "")) for row in rows if row.get("sessionDefaultChannelGroup")})
    if channel_filter:
        rows = [row for row in rows if channel_filter in str(row.get("sessionDefaultChannelGroup", "")).casefold()]
    keys = ("sessions", "totalUsers", "activeUsers", "screenPageViews", "engagedSessions")
    totals = {key: sum(_number(row.get(key)) for row in rows) for key in keys}
    totals["engagementRate"] = round(totals["engagedSessions"] / totals["sessions"], 6) if totals["sessions"] else 0
    totals["viewsPerSession"] = round(totals["screenPageViews"] / totals["sessions"], 4) if totals["sessions"] else 0
    def grouped(field: str) -> list[dict[str, Any]]:
        groups: dict[str, list[dict[str, Any]]] = {}
        for row in rows: groups.setdefault(str(row.get(field) or "(not set)"), []).append(row)
        result = []
        for label, items in groups.items():
            summary = {key: sum(_number(row.get(key)) for row in items) for key in keys}
            summary["engagementRate"] = round(summary["engagedSessions"] / summary["sessions"], 6) if summary["sessions"] else 0
            summary["viewsPerSession"] = round(summary["screenPageViews"] / summary["sessions"], 4) if summary["sessions"] else 0
            result.append({field: label, **summary})
        return result
    return {"status": "ok" if source else "no_data", "sourceFile": _relative(source), "totals": totals, "trend": sorted(grouped("date"), key=lambda item: item["date"]), "channels": sorted(grouped("sessionDefaultChannelGroup"), key=lambda item: item["sessions"], reverse=True), "rows": rows[:200], "filters": {"channels": all_channels, "channel": channel_filter}, "metadata": {"primaryConversions": "Not configured" if not load_env().get("PRIMARY_CONVERSIONS") else load_env()["PRIMARY_CONVERSIONS"], "limitations": ["GSC clicks and GA4 sessions are different measurements.", "Conversion interpretation remains incomplete until primary events are configured."]}}


def _pagespeed_run(path: Path) -> dict[str, Any] | None:
    try: data = _json(path)
    except (OSError, json.JSONDecodeError): return None
    summary = data.get("summary", {})
    scores = summary.get("scores", {}) if isinstance(summary, dict) else {}
    metrics = summary.get("coreMetrics", {}) if isinstance(summary, dict) else {}
    error_text = json.dumps(data.get("error") or data.get("lighthouseResult", {}).get("runtimeError") or "", ensure_ascii=False)
    failed = bool(data.get("error") or data.get("lighthouseResult", {}).get("runtimeError") or "timeout" in error_text.casefold())
    match = re.search(r"_(mobile|desktop)_\d{8}_\d{6}\.json$", path.name)
    fetched = str(summary.get("fetchTime") or "")
    fetched_day = _date(fetched[:10])
    age = (dt.date.today() - fetched_day).days if fetched_day else None
    return {"status": "failed" if failed else "success", "displayStatus": "Run failed" if failed else "Completed", "url": summary.get("requestedUrl", ""), "finalUrl": summary.get("finalUrl", ""), "strategy": match.group(1) if match else "", "fetchedAt": fetched, "ageDays": age, "isStale": age is None or age > 7, "scores": None if failed else {"performance": _number(scores.get("performance")), "accessibility": _number(scores.get("accessibility")), "bestPractices": _number(scores.get("best-practices")), "seo": _number(scores.get("seo"))}, "metrics": {"lcp": metrics.get("largest-contentful-paint", ""), "tbt": metrics.get("total-blocking-time", ""), "cls": metrics.get("cumulative-layout-shift", ""), "speedIndex": metrics.get("speed-index", "")}, "error": error_text[:500] if failed else "", "rawPath": _relative(path)}


def pagespeed_history(params: dict[str, list[str]]) -> dict[str, Any]:
    url_filter = params.get("url", [""])[0].strip()
    strategy_filter = params.get("strategy", [""])[0].strip().casefold()
    runs = []
    for path in sorted(RAW["pagespeed"].glob("pagespeed_*.json"), key=lambda item: item.stat().st_mtime, reverse=True) if RAW["pagespeed"].exists() else []:
        run = _pagespeed_run(path)
        if run and (not url_filter or run["url"] == url_filter) and (not strategy_filter or run["strategy"] == strategy_filter): runs.append(run)
    latest: dict[str, dict[str, Any]] = {}
    for run in runs: latest.setdefault(f"{run['url']}|{run['strategy']}", run)
    pages = []
    for item in sorted(_aggregate(_csv(_latest_gsc("page")), "page"), key=lambda item: item["impressions"], reverse=True)[:100]:
        run = next((row for row in runs if row["url"] == item["label"]), None)
        pages.append({"url": item["label"], "clicks": item["clicks"], "impressions": item["impressions"], "tested": bool(run), "latestFetchedAt": run.get("fetchedAt", "") if run else "", "isStale": run.get("isStale", True) if run else True})
    return {"status": "ok" if runs else "no_data", "runs": runs[:200], "latest": list(latest.values())[:50], "pages": pages, "sqliteRuns": recent_pagespeed_runs(30, url_filter), "metadata": {"failureSemantics": "Failed Lighthouse executions are Run failed and have no performance score."}}


def summarize_crux() -> dict[str, Any]:
    source = _latest(RAW["crux"], "crux_*.json")
    if not source:
        return {"status": "no_data", "displayStatus": "No dataset", "message": "CrUX has no field dataset for this origin/page. Lab monitoring remains available.", "sourceFile": None, "latestRun": latest_api_run("crux"), "summary": {}}
    return {"status": "ok", "displayStatus": "Field data available", "message": "CrUX cached field data available.", "sourceFile": _relative(source), "latestRun": latest_api_run("crux"), "summary": _json(source).get("summary", {})}


def _snapshot(source: str) -> set[Path]:
    directory = RAW[source]
    return {path.resolve() for path in directory.iterdir() if path.is_file()} if directory.exists() else set()


def _run(source: str, command: list[str], timeout: int = 120) -> dict[str, Any]:
    before = _snapshot(source)
    completed = subprocess.run(command, cwd=ROOT, text=True, capture_output=True, timeout=timeout, check=False)
    after = _snapshot(source)
    new_files = sorted(after - before, key=lambda item: item.stat().st_mtime)
    error = completed.stderr.strip()[:2000]
    summary: dict[str, Any] = {"returnCode": completed.returncode, "newFiles": [_relative(path) for path in new_files]}
    run_id = record_api_run(source, "ok" if completed.returncode == 0 else "error", " ".join(command[1:]), summary, _relative(new_files[-1]) if new_files else "", error)
    cloud = auto_upload_files(new_files, f"{source}_sync") if completed.returncode == 0 and is_supabase_configured() else {"ok": False, "skipped": True}
    summary["cloudSync"] = cloud
    update_api_run_summary(run_id, summary)
    return {"ok": completed.returncode == 0, "stdout": completed.stdout.strip()[-1000:], "error": error, "newFiles": summary["newFiles"], "cloudSync": cloud}


def run_gsc_sync() -> dict[str, Any]:
    results = []
    for dimensions in (("date", "query", "page"), ("query",), ("page",)):
        result = _run("gsc", [sys.executable, "tools/gsc_cli.py", "performance", "--dimensions", *dimensions, "--save", "--quiet"])
        results.append(result)
        if not result["ok"]: break
    return {"ok": all(item["ok"] for item in results), "results": results}


def run_ga4_sync() -> dict[str, Any]: return _run("ga4", [sys.executable, "tools/ga4_cli.py", "report", "--save", "--quiet"])
def run_pagespeed_sync(url: str = "", strategy: str = "mobile") -> dict[str, Any]:
    command = [sys.executable, "tools/pagespeed_cli.py", "run", "--summary", "--save", "--strategy", strategy or "mobile"]
    if url: command.extend(["--url", url])
    result = _run("pagespeed", command)
    return {**result, "history": pagespeed_history({"url": [url], "strategy": [strategy]})}
def run_crux_sync() -> dict[str, Any]: return _run("crux", [sys.executable, "tools/crux_cli.py", "query", "--form-factor", "ALL", "--summary", "--save"], 60)


def generate_ai_task(payload: dict[str, Any]) -> dict[str, Any]:
    TASK_DIR.mkdir(parents=True, exist_ok=True)
    title = str(payload.get("title") or "Scoped SEO analysis")
    task_type = str(payload.get("taskType") or "seo_analysis")
    scope = payload.get("scope") or {}
    evidence = payload.get("evidence") or {}
    stamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    path = TASK_DIR / f"{stamp}_{re.sub(r'[^a-z0-9]+', '_', task_type.casefold()).strip('_')}.md"
    content = f"# {title}\n\nTask type: `{task_type}`\n\n## Scope\n\n```json\n{json.dumps(scope, ensure_ascii=False, indent=2)}\n```\n\n## Evidence\n\n```json\n{json.dumps(evidence, ensure_ascii=False, indent=2)}\n```\n\nAnalyze observations, limitations, likely explanations, evidence still required, recommended action, and verification window. Do not invent metrics or causation.\n"
    path.write_text(content, encoding="utf-8")
    return {"ok": True, "path": _relative(path), "title": title, "taskType": task_type, "createdAt": dt.datetime.now().isoformat(timespec="seconds")}


def recent_ai_tasks(limit: int = 30) -> list[dict[str, Any]]:
    files = sorted(TASK_DIR.glob("*.md"), key=lambda item: item.stat().st_mtime, reverse=True) if TASK_DIR.exists() else []
    return [{"name": path.name, "path": _relative(path), "modified": dt.datetime.fromtimestamp(path.stat().st_mtime).isoformat(timespec="seconds"), "bytes": path.stat().st_size} for path in files[:limit]]


def status() -> dict[str, Any]:
    exports = sorted(RAW["gsc"].glob("gsc_*.csv"), key=lambda item: item.stat().st_mtime, reverse=True) if RAW["gsc"].exists() else []
    return {"exports": [{"name": path.name, "path": _relative(path), "bytes": path.stat().st_size, "modified": dt.datetime.fromtimestamp(path.stat().st_mtime).isoformat(timespec="seconds")} for path in exports[:10]], "recentRuns": recent_api_runs(10)}
