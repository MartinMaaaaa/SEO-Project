from __future__ import annotations

import csv
import datetime as dt
import json
from pathlib import Path
import re
import subprocess
import sys
import threading
from typing import Any

from apps.api.core.config import ROOT, load_env
from apps.api.db.cloud_sync import auto_upload_files, is_supabase_configured
from apps.api.db import ga4_store, gsc_store
from apps.api.db.local_store import latest_api_run, latest_successful_api_run, recent_api_runs, recent_pagespeed_runs, record_api_run, record_pagespeed_run, update_api_run_summary

RAW = {name: ROOT / "data" / name / "raw" for name in ("gsc", "ga4", "pagespeed", "crux")}
TASK_DIR = ROOT / ".ai" / "runtime_tasks"
SYNC_LOCKS = {source: threading.Lock() for source in ("gsc", "ga4", "pagespeed", "crux")}


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
    if not path:
        return None
    try:
        return str(path.resolve().relative_to(ROOT)).replace("\\", "/")
    except ValueError:
        return str(path.resolve()).replace("\\", "/")


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
        raw_now, raw_before = current.get(metric), previous.get(metric)
        result[f"previous_{metric}"] = raw_before
        if raw_now is None or raw_before is None:
            result[f"delta_{metric}"] = None
            result[f"change_{metric}"] = None
            continue
        now, before = _number(raw_now), _number(raw_before)
        delta = now - before
        result[f"previous_{metric}"] = round(before, 6)
        result[f"delta_{metric}"] = round(delta, 6)
        result[f"change_{metric}"] = round(delta / before, 6) if before else None
    result["click_contribution"] = round(_number(result["delta_clicks"]) / total_click_delta, 6) if total_click_delta and result.get("delta_clicks") is not None else None
    return result


def _comparison_table(
    current_rows: list[dict[str, str]],
    previous_rows: list[dict[str, str]],
    field: str,
    total_click_delta: float,
    comparison_complete: bool,
) -> list[dict[str, Any]]:
    current = {item["label"]: item for item in _aggregate(current_rows, field)}
    previous = {item["label"]: item for item in _aggregate(previous_rows, field)} if comparison_complete else {}
    labels = set(current) | set(previous)
    result = []
    for label in labels:
        now_present, before_present = label in current, label in previous
        now = current.get(label, {"label": label, "clicks": 0, "impressions": 0, "ctr": None, "position": None, "rows": 0})
        before = previous.get(label, {"label": label, "clicks": 0, "impressions": 0, "ctr": None, "position": None, "rows": 0})
        item = {**now}
        if comparison_complete:
            item.update(_delta(now, before, total_click_delta))
            if now_present and not before_present:
                item["movement"] = "new"
            elif before_present and not now_present:
                item["movement"] = "lost"
            elif _number(item.get("delta_clicks")) > 0:
                item["movement"] = "increased"
            elif _number(item.get("delta_clicks")) < 0:
                item["movement"] = "declined"
            else:
                item["movement"] = "stable"
        else:
            item["movement"] = "comparison_unavailable"
        item["nearFirstPage"] = now.get("position") is not None and _number(now.get("impressions")) > 0 and 10 < _number(now.get("position")) <= 20
        result.append(item)
    return result


def _opportunity_groups(rows: list[dict[str, Any]], comparison_complete: bool) -> dict[str, Any]:
    keys = ("increased", "declined", "new", "lost")
    groups = {key: [row for row in rows if row.get("movement") == key] for key in keys}
    groups["nearFirstPage"] = [row for row in rows if row.get("nearFirstPage")]
    return {
        "status": "available" if comparison_complete else "comparison_unavailable",
        "definitions": {"nearFirstPage": "Current impression-weighted Position is greater than 10 and at most 20."},
        "groups": groups,
        "counts": {key: len(value) for key, value in groups.items()},
    }


def _alignment_offset(day: dt.date, anchor: dt.date, grain: str) -> int:
    if grain == "week":
        day_week = day - dt.timedelta(days=day.weekday())
        anchor_week = anchor - dt.timedelta(days=anchor.weekday())
        return (day_week - anchor_week).days // 7
    if grain == "month":
        return (day.year - anchor.year) * 12 + day.month - anchor.month
    return (day - anchor).days


def _trend_period(rows: list[dict[str, str]], grain: str, period_start: dt.date | None = None) -> list[dict[str, Any]]:
    """Aggregate one contracted period with stable calendar offsets.

    Offsets are derived from the requested period start rather than from the
    position of observed buckets, so a missing source bucket remains missing
    and cannot shift later current/comparison values into a false alignment.
    """
    groups: dict[str, list[dict[str, str]]] = {}
    dates: dict[str, list[dt.date]] = {}
    for row in rows:
        day = _date(row.get("date", ""))
        if not day:
            continue
        if grain == "week":
            year, week, _ = day.isocalendar()
            label = f"{year}-W{week:02d}"
        elif grain == "month":
            label = day.strftime("%Y-%m")
        else:
            label = day.isoformat()
        groups.setdefault(label, []).append(row)
        dates.setdefault(label, []).append(day)
    result = []
    anchor = period_start or min((day for values in dates.values() for day in values), default=None)
    for label in sorted(groups):
        observed = dates[label]
        bucket_start = min(observed)
        result.append({
            "label": label,
            "alignmentKey": f"{grain}:{_alignment_offset(bucket_start, anchor, grain) if anchor else 0}",
            "periodStart": bucket_start.isoformat(),
            "periodEnd": max(observed).isoformat(),
            **_metrics(groups[label]),
        })
    return result


def _comparison_reason(status: str) -> tuple[str | None, str | None]:
    reasons = {
        "partial": (
            "partial_cache_coverage",
            "Comparison range is only partially covered by the local cache; comparison values are suppressed.",
        ),
        "unavailable": (
            "outside_cache_coverage",
            "Comparison range is outside local cache coverage; comparison values are suppressed.",
        ),
        "none": ("disabled", "Comparison is disabled."),
    }
    return reasons.get(status, (None, None))


def _comparison_trend_table(
    current_trend: list[dict[str, Any]],
    comparison_trend: list[dict[str, Any]],
    total_click_delta: float,
    comparison_complete: bool,
) -> list[dict[str, Any]]:
    """Build the Date table from the exact chart aggregates and alignment keys."""
    previous = {row["alignmentKey"]: row for row in comparison_trend}
    result: list[dict[str, Any]] = []
    for current in current_trend:
        item = {**current}
        before = previous.get(current["alignmentKey"]) if comparison_complete else None
        item["comparisonLabel"] = before.get("label") if before else None
        if before:
            item.update(_delta(current, before, total_click_delta))
            item["movement"] = "increased" if item["delta_clicks"] > 0 else "declined" if item["delta_clicks"] < 0 else "stable"
        else:
            for metric in ("clicks", "impressions", "ctr", "position"):
                item[f"previous_{metric}"] = None
                item[f"delta_{metric}"] = None
                item[f"change_{metric}"] = None
            item["click_contribution"] = None
            item["movement"] = "comparison_unavailable"
        result.append(item)
    return result


def gsc_explorer(params: dict[str, list[str]]) -> dict[str, Any]:
    source = _latest_gsc("date-query-page")
    rows = _csv(source)
    dated = [(row, _date(row.get("date", ""))) for row in rows]
    dated = [(row, day) for row, day in dated if day]
    if not dated:
        return {"status": "no_data", "totals": _metrics([]), "trend": [], "tables": {"query": [], "page": [], "date": [], "country": [], "device": [], "searchAppearance": []}, "metadata": {"availableDimensions": {"date": False, "query": False, "page": False, "country": False, "device": False, "searchAppearance": False}, "dimensionCapabilities": {}, "limitations": ["No cached date + query + page export is available."]}}
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
    trend = _trend_period(scoped, grain, start)
    comparison_trend = _trend_period(previous_rows, grain, _date(previous_range["start"]) if previous_range else None) if comparison_status == "complete" else []
    limit = max(1, min(int(float(params.get("limit", ["50"])[0] or 50)), 200))
    sort_key = params.get("sort", ["clicks"])[0]
    tables = {}
    for field in ("query", "page"):
        combined = _comparison_table(scoped, previous_rows, field, total_click_delta, comparison_status == "complete")
        tables[field] = sorted(combined, key=lambda item: _number(item.get(sort_key)), reverse=sort_key != "position")[:limit]
    tables["date"] = _comparison_trend_table(trend, comparison_trend, total_click_delta, comparison_status == "complete")[:limit]
    dimensions = gsc_store.dimension_breakdowns(start, end, previous_range, comparison_status, filters)
    tables.update({key: value[:limit] for key, value in dimensions["tables"].items()})
    capabilities = dimensions["capabilities"]
    available_dimensions = {"date": True, "query": True, "page": True, **{key: bool(value.get("enabled")) for key, value in capabilities.items()}}
    limitations = [
        "Query and Page use the date + query + page cache grain.",
        "Country and Device use separate property-level date grains; Search Appearance uses the official two-step discovery and filtered-date grain.",
        "Separate grains are never joined to invent a combined breakdown.",
        "Comparison values are suppressed when baseline coverage is unavailable.",
        "Anonymous queries and API row limits can make table totals differ from GSC chart totals.",
        "CTR is recomputed; position is impression-weighted.",
        *dimensions["notices"],
    ]
    comparison_reason_code, comparison_reason = _comparison_reason(comparison_status)
    current_partial = start < coverage_start or end > coverage_end
    today = dt.datetime.now(dt.timezone.utc).date()
    stale_after_days = 3
    latest_attempt = latest_api_run("gsc")
    latest_success = latest_successful_api_run("gsc")
    return {
        "status": "ok",
        "totals": totals,
        "previousTotals": previous_totals,
        "deltas": _delta(totals, previous_totals, total_click_delta) if previous_totals else None,
        "trend": trend,
        "comparisonTrend": comparison_trend,
        "tables": tables,
        "opportunities": {
            "query": _opportunity_groups(tables["query"], comparison_status == "complete"),
            "page": _opportunity_groups(tables["page"], comparison_status == "complete"),
        },
        "comparison": {
            "mode": comparison_mode,
            "status": comparison_status,
            "range": previous_range,
            "reasonCode": comparison_reason_code,
            "reason": comparison_reason,
            "alignment": "backend_offset_key",
        },
        "scope": {
            "range": {"start": start.isoformat(), "end": end.isoformat()},
            "effectiveRange": {
                "start": max(start, coverage_start).isoformat(),
                "end": min(end, coverage_end).isoformat(),
            },
            "filters": filters,
            "grain": grain,
            "rowLimit": limit,
        },
        "metadata": {
            "source": "Google Search Console cached export",
            "property": load_env().get("GSC_SITE_URL", "Unknown"),
            "sourceFile": _relative(source),
            "timezone": "America/Los_Angeles (GSC reporting)",
            "grain": grain,
            "cacheCoverage": {"start": coverage_start.isoformat(), "end": coverage_end.isoformat()},
            "latestCompleteDate": coverage_end.isoformat(),
            "freshness": dt.datetime.fromtimestamp(source.stat().st_mtime).isoformat(timespec="seconds"),
            "lastAttemptAt": latest_attempt.get("created_at") if latest_attempt else None,
            "lastSuccessAt": latest_success.get("created_at") if latest_success else None,
            "sourceLatency": "Search Console data is not zero-latency; the latest complete date follows the newest cached API export and may lag Google processing.",
            "dataQuality": {
                "coverageStatus": "partial" if current_partial else "complete",
                "partialReasonCode": "current_outside_cache_coverage" if current_partial else None,
                "isStale": (today - coverage_end).days > stale_after_days,
                "staleAfterDays": stale_after_days,
            },
            "availableDimensions": available_dimensions,
            "dimensionCapabilities": capabilities,
            "limitations": limitations,
        },
    }


def gsc_detail(entity_type: str, value: str, params: dict[str, list[str]]) -> dict[str, Any]:
    if entity_type not in {"query", "page"}:
        return {"status": "invalid", "message": "entityType must be query or page"}
    filters = [{"field": entity_type, "operator": "equals", "value": value}]
    detail_params = {**params, "query": [""], "page": [""], "filters": [json.dumps(filters)]}
    detail = gsc_explorer(detail_params)
    related_dimension = "page" if entity_type == "query" else "query"
    return {
        "status": detail.get("status"),
        "entityType": entity_type,
        "value": value,
        "title": "Keyword Detail" if entity_type == "query" else "Page Detail",
        "totals": detail.get("totals", {}),
        "previousTotals": detail.get("previousTotals"),
        "deltas": detail.get("deltas"),
        "trend": detail.get("trend", []),
        "comparisonTrend": detail.get("comparisonTrend", []),
        "scope": detail.get("scope", {}),
        "comparison": detail.get("comparison", {}),
        "related": {"dimension": related_dimension, "label": "Ranking Pages" if entity_type == "query" else "Query Portfolio", "rows": detail.get("tables", {}).get(related_dimension, [])},
        "opportunities": detail.get("opportunities", {}).get(related_dimension, {}),
        "dimensionCapabilities": detail.get("metadata", {}).get("dimensionCapabilities", {}),
        "limitations": [
            "Keyword/Page relationships use only the cached date + query + page grain.",
            "New and lost mean observed in one complete comparison period but not the other; API limits and anonymization can affect membership.",
            *detail.get("metadata", {}).get("limitations", []),
        ],
        "freshness": detail.get("metadata", {}).get("freshness"),
        "metadata": {
            "timezone": detail.get("metadata", {}).get("timezone"),
            "grain": detail.get("metadata", {}).get("grain"),
            "latestCompleteDate": detail.get("metadata", {}).get("latestCompleteDate"),
            "dataQuality": detail.get("metadata", {}).get("dataQuality", {}),
        },
    }


GA4_COUNT_METRICS = ("sessions", "totalUsers", "newUsers", "engagedSessions", "screenPageViews", "keyEvents")
GA4_STANDARD_METRICS = ("sessions", "totalUsers", "newUsers", "engagedSessions", "screenPageViews")
GA4_REPORT_DIMENSIONS = {
    "totals": "sessionDefaultChannelGroup",
    "source-medium": "sessionSourceMedium",
    "landing-page": "landingPagePlusQueryString",
    "device": "deviceCategory",
    "country": "country",
}


def _ga4_payloads() -> list[tuple[Path, dict[str, Any]]]:
    result: list[tuple[Path, dict[str, Any]]] = []
    paths = sorted(RAW["ga4"].glob("ga4_*.json"), key=lambda item: item.stat().st_mtime, reverse=True) if RAW["ga4"].exists() else []
    for path in paths:
        try:
            payload = _json(path)
        except (OSError, json.JSONDecodeError):
            continue
        if isinstance(payload, dict):
            result.append((path, payload))
    return result


def _ga4_dimensions(payload: dict[str, Any]) -> list[str]:
    return [str(item.get("name") or "") for item in payload.get("response", {}).get("dimensionHeaders", [])]


def _ga4_report(label: str) -> tuple[Path | None, dict[str, Any]]:
    payloads = _ga4_payloads()
    for path, payload in payloads:
        if str(payload.get("reportLabel") or "").casefold() == label.casefold():
            return path, payload
    if label in {"totals", "trend"}:
        for path, payload in payloads:
            dimensions = _ga4_dimensions(payload)
            if "date" in dimensions and "sessionDefaultChannelGroup" in dimensions:
                return path, payload
    return None, {}


def _ga4_rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
    response = payload.get("response", {}) if isinstance(payload, dict) else {}
    dimensions = [str(item.get("name") or "") for item in response.get("dimensionHeaders", [])]
    metrics = [str(item.get("name") or "") for item in response.get("metricHeaders", [])]
    result: list[dict[str, Any]] = []
    for row in response.get("rows", []):
        item: dict[str, Any] = {}
        dimension_values = row.get("dimensionValues", [])
        metric_values = row.get("metricValues", [])
        for index, name in enumerate(dimensions):
            value = dimension_values[index].get("value", "") if index < len(dimension_values) else ""
            item[name] = _date(value).isoformat() if name == "date" and _date(value) else value
        for index, name in enumerate(metrics):
            item[name] = _number(metric_values[index].get("value")) if index < len(metric_values) else None
        result.append(item)
    return result


def _ga4_ranges(payload: dict[str, Any]) -> tuple[dict[str, str] | None, dict[str, str] | None]:
    ranges = payload.get("request", {}).get("dateRanges", []) if isinstance(payload, dict) else []
    current = next((item for item in ranges if item.get("name") == "current"), ranges[0] if ranges else None)
    comparison = next((item for item in ranges if item.get("name") == "comparison"), ranges[1] if len(ranges) > 1 else None)
    normalize = lambda item: {"start": str(item.get("startDate") or ""), "end": str(item.get("endDate") or "")} if item else None
    return normalize(current), normalize(comparison)


def _ga4_period(row: dict[str, Any]) -> str:
    value = str(row.get("dateRange") or "current")
    if value in {"date_range_1", "comparison"}: return "comparison"
    return "current"


def _ga4_summary(rows: list[dict[str, Any]], *, include_key_events: bool = False) -> dict[str, Any]:
    metrics = (*GA4_STANDARD_METRICS, "keyEvents") if include_key_events else GA4_STANDARD_METRICS
    summary: dict[str, Any] = {key: round(sum(_number(row.get(key)) for row in rows), 6) for key in metrics}
    sessions = _number(summary.get("sessions"))
    engaged = _number(summary.get("engagedSessions"))
    views = _number(summary.get("screenPageViews"))
    summary["engagementRate"] = round(engaged / sessions, 6) if sessions else None
    summary["viewsPerSession"] = round(views / sessions, 6) if sessions else None
    return summary


def _ga4_delta(current: dict[str, Any], previous: dict[str, Any] | None, metrics: tuple[str, ...]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for metric in metrics:
        before = previous.get(metric) if previous else None
        now = current.get(metric)
        result[f"previous_{metric}"] = before
        if before is None or now is None:
            result[f"delta_{metric}"] = None
            result[f"change_{metric}"] = None
            continue
        delta = _number(now) - _number(before)
        result[f"delta_{metric}"] = round(delta, 6)
        result[f"change_{metric}"] = round(delta / _number(before), 6) if _number(before) else None
    return result


def _ga4_period_table(payload: dict[str, Any], field: str, include_key_events: bool = False) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for row in _ga4_rows(payload):
        grouped.setdefault((_ga4_period(row), str(row.get(field) or "(not set)")), []).append(row)
    current = {label: _ga4_summary(rows, include_key_events=include_key_events) for (period, label), rows in grouped.items() if period == "current"}
    previous = {label: _ga4_summary(rows, include_key_events=include_key_events) for (period, label), rows in grouped.items() if period == "comparison"}
    metrics = (*GA4_STANDARD_METRICS, "engagementRate", "keyEvents") if include_key_events else (*GA4_STANDARD_METRICS, "engagementRate")
    rows: list[dict[str, Any]] = []
    for label in sorted(set(current) | set(previous)):
        now = current.get(label) or {**{key: 0 for key in GA4_STANDARD_METRICS}, "engagementRate": None, "viewsPerSession": None}
        before = previous.get(label)
        rows.append({"label": label, field: label, **now, **_ga4_delta(now, before, metrics)})
    return sorted(rows, key=lambda item: _number(item.get("sessions")), reverse=True)


def _ga4_trends(payload: dict[str, Any], conversion_payload: dict[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    current_range, comparison_range = _ga4_ranges(payload)
    conversion_by_period_date: dict[tuple[str, str], float] = {}
    for row in _ga4_rows(conversion_payload):
        key = (_ga4_period(row), str(row.get("date") or ""))
        conversion_by_period_date[key] = conversion_by_period_date.get(key, 0) + _number(row.get("keyEvents"))
    result = {"current": [], "comparison": []}
    for row in _ga4_rows(payload):
        date = _date(str(row.get("date") or ""))
        if not date:
            continue
        period = _ga4_period(row)
        period_range = current_range if period == "current" else comparison_range
        anchor = _date(period_range["start"]) if period_range else date
        summary = {key: row.get(key) for key in GA4_STANDARD_METRICS}
        summary["engagementRate"] = round(_number(summary.get("engagedSessions")) / _number(summary.get("sessions")), 6) if _number(summary.get("sessions")) else None
        if conversion_payload:
            summary["keyEvents"] = conversion_by_period_date.get((period, date.isoformat()))
        result[period].append({
            "date": date.isoformat(), "label": date.isoformat(), "periodStart": date.isoformat(), "periodEnd": date.isoformat(),
            "alignmentKey": f"day:{(date - anchor).days}", **summary,
        })
    return sorted(result["current"], key=lambda item: item["date"]), sorted(result["comparison"], key=lambda item: item["date"])


def _configured_events() -> list[str]:
    return [item.strip() for item in load_env().get("PRIMARY_CONVERSIONS", "").split(",") if item.strip()]


def ga4_analytics(params: dict[str, list[str]]) -> dict[str, Any]:
    totals_path, totals_payload = _ga4_report("totals")
    trend_path, trend_payload = _ga4_report("trend")
    configured_events = _configured_events()
    conversion_path, conversion_payload = _ga4_report("configured-key-events") if configured_events else (None, {})
    source = trend_path or totals_path
    if not source:
        return {
            "status": "no_data", "sourceFile": None, "totals": {}, "previousTotals": None,
            "trend": [], "comparisonTrend": [], "tables": {key: [] for key in ("channel", "sourceMedium", "landingPage", "device", "country")},
            "metadata": {"conversionState": "not_configured" if not configured_events else "not_collected", "primaryConversions": "Not configured" if not configured_events else configured_events},
        }

    current_range, comparison_range = _ga4_ranges(totals_payload or trend_payload)
    totals_rows = _ga4_rows(totals_payload)
    current_totals = _ga4_summary([row for row in totals_rows if _ga4_period(row) == "current"])
    previous_rows = [row for row in totals_rows if _ga4_period(row) == "comparison"]
    previous_totals = _ga4_summary(previous_rows) if previous_rows else None
    if conversion_payload:
        conversion_rows = _ga4_rows(conversion_payload)
        current_totals["keyEvents"] = round(sum(_number(row.get("keyEvents")) for row in conversion_rows if _ga4_period(row) == "current"), 6)
        if previous_totals is not None:
            previous_totals["keyEvents"] = round(sum(_number(row.get("keyEvents")) for row in conversion_rows if _ga4_period(row) == "comparison"), 6)
    trend, comparison_trend = _ga4_trends(trend_payload or totals_payload, conversion_payload)
    reports = {
        "channel": ("totals", "sessionDefaultChannelGroup"),
        "sourceMedium": ("source-medium", "sessionSourceMedium"),
        "landingPage": ("landing-page", "landingPagePlusQueryString"),
        "device": ("device", "deviceCategory"),
        "country": ("country", "country"),
    }
    tables: dict[str, list[dict[str, Any]]] = {}
    capabilities: dict[str, dict[str, Any]] = {}
    source_files: list[str] = []
    for key, (label, field) in reports.items():
        path, payload = _ga4_report(label)
        available = bool(path and field in _ga4_dimensions(payload))
        tables[key] = _ga4_period_table(payload, field) if available else []
        capabilities[key] = {"available": available, "grain": [field, "dateRange"], "sourceFile": _relative(path)}
        if path:
            source_files.append(_relative(path) or "")
    if conversion_payload:
        conversion_landing = _ga4_period_table(conversion_payload, "landingPagePlusQueryString", include_key_events=True)
        conversion_by_landing = {row["label"]: row for row in conversion_landing}
        for row in tables["landingPage"]:
            converted = conversion_by_landing.get(row["label"], {})
            for key in ("keyEvents", "previous_keyEvents", "delta_keyEvents", "change_keyEvents"):
                row[key] = converted.get(key)
    comparison_status = "complete" if comparison_range and previous_totals is not None else "unavailable"
    latest_attempt = latest_api_run("ga4")
    latest_success = latest_successful_api_run("ga4")
    conversion_state = "not_configured" if not configured_events else "available" if conversion_payload else "not_collected"
    metrics = ["sessions", "totalUsers", "newUsers", "engagedSessions", "engagementRate", "screenPageViews"]
    if conversion_state == "available": metrics.append("keyEvents")
    limitations = [
        "GSC clicks and GA4 sessions are different measurements.",
        "GA4 reporting identity, consent, thresholds, retention, and processing latency can affect results.",
        "Each table uses its own API-validated dimension grain; dimensions are not cross-joined.",
        "Engagement rate is recomputed as engaged sessions divided by sessions.",
    ]
    if conversion_state == "not_configured": limitations.append("Primary key events/conversions are Not configured; engagement is not used as a substitute.")
    elif conversion_state == "not_collected": limitations.append("Primary key events are configured but have not been collected by the latest compatible cached report.")
    return {
        "status": "ok", "sourceFile": _relative(source), "sourceFiles": sorted(set(source_files)),
        "totals": current_totals, "previousTotals": previous_totals,
        "deltas": _ga4_delta(current_totals, previous_totals, tuple(metrics)) if previous_totals else None,
        "trend": trend, "comparisonTrend": comparison_trend, "tables": tables,
        "channels": tables["channel"], "rows": tables["landingPage"] or tables["channel"],
        "comparison": {"mode": "previous_period", "status": comparison_status, "range": comparison_range, "alignment": "backend_offset_key"},
        "scope": {"range": current_range, "comparisonRange": comparison_range, "segment": "Organic Search", "grain": "day", "rowLimit": 10000},
        "filters": {"channel": "Organic Search"},
        "metadata": {
            "source": "Google Analytics Data API cached exports", "metrics": metrics,
            "dimensionCapabilities": capabilities, "primaryConversions": configured_events if configured_events else "Not configured",
            "conversionState": conversion_state, "timezone": "Unknown (GA4 property timezone is not collected)",
            "latestCompleteDate": current_range.get("end") if current_range else None,
            "freshness": dt.datetime.fromtimestamp(source.stat().st_mtime).isoformat(timespec="seconds"),
            "lastAttemptAt": latest_attempt.get("created_at") if latest_attempt else None,
            "lastSuccessAt": latest_success.get("created_at") if latest_success else None,
            "sourceLatency": "Latest complete date is conservatively limited to two days ago; GA4 processing, identity, consent, and thresholds can still affect results.",
            "limitations": limitations,
        },
    }


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
    try:
        completed = subprocess.run(command, cwd=ROOT, text=True, capture_output=True, timeout=timeout, check=False)
    except (subprocess.TimeoutExpired, OSError) as exc:
        error = f"{type(exc).__name__}: {exc}"[:2000]
        summary = {"returnCode": None, "newFiles": [], "cloudSync": {"ok": False, "skipped": True}}
        run_id = record_api_run(source, "error", " ".join(command[1:]), summary, "", error)
        return {"ok": False, "status": "error", "runId": run_id, "stdout": "", "error": error, "newFiles": [], "cloudSync": summary["cloudSync"], "localPersistence": {"rawFiles": 0, "apiRunRecorded": True}}
    after = _snapshot(source)
    new_files = sorted(after - before, key=lambda item: item.stat().st_mtime)
    error = completed.stderr.strip()[:2000]
    summary: dict[str, Any] = {"returnCode": completed.returncode, "newFiles": [_relative(path) for path in new_files]}
    run_id = record_api_run(source, "ok" if completed.returncode == 0 else "error", " ".join(command[1:]), summary, _relative(new_files[-1]) if new_files else "", error)
    cloud = auto_upload_files(new_files, f"{source}_sync") if completed.returncode == 0 and is_supabase_configured() else {"ok": False, "skipped": True}
    summary["cloudSync"] = cloud
    update_api_run_summary(run_id, summary)
    return {
        "ok": completed.returncode == 0, "status": "success" if completed.returncode == 0 else "error", "runId": run_id,
        "stdout": completed.stdout.strip()[-1000:], "error": error, "newFiles": summary["newFiles"], "cloudSync": cloud,
        "localPersistence": {"rawFiles": len(new_files), "apiRunRecorded": True},
    }


def _normalize_gsc_result(result: dict[str, Any]) -> dict[str, Any]:
    if not result.get("ok"):
        return result
    paths = [ROOT / str(item) for item in result.get("newFiles", []) if str(item).casefold().endswith(".json")]
    try:
        imports = gsc_store.import_exports(paths)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        return {**result, "ok": False, "normalizationError": str(exc)[:500]}
    return {**result, "normalizedImports": imports}


def _normalize_ga4_result(result: dict[str, Any]) -> dict[str, Any]:
    if not result.get("ok"):
        return result
    paths = [ROOT / str(item) for item in result.get("newFiles", []) if str(item).casefold().endswith(".json")]
    try:
        imports = ga4_store.import_exports(paths, source_run_id=result.get("runId"))
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        return {**result, "ok": False, "status": "partial", "normalizationError": str(exc)[:500]}
    return {**result, "normalizedImports": imports, "localPersistence": {**result.get("localPersistence", {}), "normalizedImports": len(imports)}}


def _run_gsc_query(dimensions: tuple[str, ...], filters: tuple[str, ...] = ()) -> dict[str, Any]:
    command = [sys.executable, "tools/gsc_cli.py", "performance", "--dimensions", *dimensions]
    for value in filters:
        command.extend(["--filter", value])
    command.extend(["--save", "--quiet"])
    return _normalize_gsc_result(_run("gsc", command))


def _appearance_values(result: dict[str, Any]) -> list[str]:
    json_path = next((ROOT / str(item) for item in result.get("newFiles", []) if str(item).casefold().endswith(".json")), None)
    if not json_path or not json_path.exists():
        return []
    try:
        response = _json(json_path).get("response", {})
    except (OSError, json.JSONDecodeError):
        return []
    return sorted({str(row.get("keys", [""])[0]) for row in response.get("rows", []) if row.get("keys") and str(row.get("keys", [""])[0])})


def _fresh_sync_skip(source: str, force: bool, minimum_hours: int = 12) -> dict[str, Any] | None:
    if force:
        return None
    latest = latest_successful_api_run(source)
    if not latest:
        return None
    try:
        completed_at = dt.datetime.fromisoformat(str(latest.get("created_at") or ""))
    except ValueError:
        return None
    age = dt.datetime.now() - completed_at
    if age.total_seconds() >= minimum_hours * 3600:
        return None
    summary = {"reason": "freshness", "minimumHours": minimum_hours, "latestSuccessAt": latest.get("created_at")}
    run_id = record_api_run(source, "skipped", "freshness policy", summary)
    return {
        "ok": True, "status": "skipped_fresh", "skipped": True, "reason": "Fresh cached source data is inside the sync cadence.",
        "runId": run_id, "lastAttemptAt": dt.datetime.now().isoformat(timespec="seconds"), "lastSuccessAt": latest.get("created_at"),
        "localPersistence": {"rawFiles": 0, "normalizedImports": 0, "apiRunRecorded": True}, "cloudSync": {"ok": False, "skipped": True},
    }


def run_gsc_sync(force: bool = False) -> dict[str, Any]:
    """Refresh baseline grains plus truthful property-level dimension grains.

    Search Appearance follows Google's two-step contract: discover appearance
    values first, then query the date grain once per returned appearance filter.
    """
    lock = SYNC_LOCKS["gsc"]
    if not lock.acquire(blocking=False):
        return {"ok": False, "status": "in_progress", "reason": "A GSC source sync is already running."}
    try:
        skipped = _fresh_sync_skip("gsc", force)
        if skipped:
            return skipped
        results: list[dict[str, Any]] = []
        for dimensions in (("date", "query", "page"), ("query",), ("page",), ("date", "country"), ("date", "device")):
            result = _run_gsc_query(dimensions)
            results.append(result)
            if not result["ok"]:
                break
        if results and all(item["ok"] for item in results):
            discovery = _run_gsc_query(("searchAppearance",))
            results.append(discovery)
            if discovery["ok"]:
                for appearance in _appearance_values(discovery):
                    result = _run_gsc_query(("date",), (f"searchAppearance:equals:{appearance}",))
                    results.append(result)
                    if not result["ok"]:
                        break
        successes = sum(1 for item in results if item.get("ok"))
        status = "success" if results and successes == len(results) else "partial" if successes else "error"
        refreshed = gsc_explorer({"preset": ["28"], "comparison": ["previous_period"], "grain": ["day"], "limit": ["100"]}) if successes else None
        return {
            "ok": status == "success", "status": status, "results": results, "apiCalls": len(results),
            "runIds": [item.get("runId") for item in results if item.get("runId")],
            "localPersistence": {"rawFiles": sum(len(item.get("newFiles", [])) for item in results), "normalizedImports": sum(len(item.get("normalizedImports", [])) for item in results), "apiRunRecorded": bool(results)},
            "cloudSync": [item.get("cloudSync", {}) for item in results],
            "freshness": refreshed.get("metadata", {}) if refreshed else {},
            "collectionContract": {
                "country": ["date", "country"], "device": ["date", "device"],
                "searchAppearance": ["searchAppearance discovery", "date filtered by each returned appearance"], "combinedGrainInferred": False,
            },
        }
    finally:
        lock.release()


def _run_ga4_query(
    label: str,
    dimensions: tuple[str, ...],
    metrics: tuple[str, ...],
    current_range: dict[str, str],
    comparison_range: dict[str, str],
    *,
    organic_only: bool = True,
    event_names: tuple[str, ...] = (),
) -> dict[str, Any]:
    command = [
        sys.executable, "tools/ga4_cli.py", "report", "--label", label,
        "--start", current_range["start"], "--end", current_range["end"],
        "--compare-start", comparison_range["start"], "--compare-end", comparison_range["end"],
        "--dimensions", *dimensions, "--metrics", *metrics, "--limit", "10000", "--save", "--quiet",
    ]
    if organic_only:
        command.append("--organic-only")
    if event_names:
        command.extend(["--event-names", ",".join(event_names)])
    return _normalize_ga4_result(_run("ga4", command))


def run_ga4_sync(force: bool = False) -> dict[str, Any]:
    lock = SYNC_LOCKS["ga4"]
    if not lock.acquire(blocking=False):
        return {"ok": False, "status": "in_progress", "reason": "A GA4 source sync is already running."}
    try:
        skipped = _fresh_sync_skip("ga4", force)
        if skipped:
            return skipped
        end = dt.date.today() - dt.timedelta(days=2)
        start = end - dt.timedelta(days=27)
        comparison_end = start - dt.timedelta(days=1)
        comparison_start = comparison_end - dt.timedelta(days=27)
        current_range = {"start": start.isoformat(), "end": end.isoformat()}
        comparison_range = {"start": comparison_start.isoformat(), "end": comparison_end.isoformat()}
        metrics = ("sessions", "totalUsers", "newUsers", "engagedSessions", "engagementRate", "screenPageViews")
        specs = [
            ("totals", ("sessionDefaultChannelGroup",), metrics),
            ("trend", ("date",), metrics),
            ("source-medium", ("sessionSourceMedium",), metrics),
            ("landing-page", ("landingPagePlusQueryString",), metrics),
            ("device", ("deviceCategory",), metrics),
            ("country", ("country",), metrics),
        ]
        results: list[dict[str, Any]] = []
        for label, dimensions, report_metrics in specs:
            result = _run_ga4_query(label, dimensions, report_metrics, current_range, comparison_range)
            results.append(result)
            if not result.get("ok"):
                break
        configured_events = tuple(_configured_events())
        if configured_events and results and all(item.get("ok") for item in results):
            results.append(_run_ga4_query(
                "configured-key-events", ("date", "landingPagePlusQueryString", "eventName"), ("keyEvents",),
                current_range, comparison_range, event_names=configured_events,
            ))
        successes = sum(1 for item in results if item.get("ok"))
        status = "success" if results and successes == len(results) else "partial" if successes else "error"
        analysis = ga4_analytics({}) if successes else None
        return {
            "ok": status == "success", "status": status, "results": results, "apiCalls": len(results),
            "runIds": [item.get("runId") for item in results if item.get("runId")],
            "localPersistence": {"rawFiles": sum(len(item.get("newFiles", [])) for item in results), "normalizedImports": sum(len(item.get("normalizedImports", [])) for item in results), "apiRunRecorded": bool(results)},
            "cloudSync": [item.get("cloudSync", {}) for item in results],
            "freshness": analysis.get("metadata", {}) if analysis else {"latestCompleteDate": current_range["end"]},
            "collectionContract": {
                "scope": "Organic Search", "dateRanges": {"current": current_range, "comparison": comparison_range},
                "reports": {label: list(dimensions) for label, dimensions, _ in specs},
                "configuredKeyEvents": list(configured_events), "combinedGrainInferred": False,
            },
        }
    finally:
        lock.release()
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
