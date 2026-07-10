from __future__ import annotations

import datetime as dt
from typing import Any

from apps.api.core.config import settings
from apps.api.db import cloud, local_backup


POLICIES = {
    "gsc": {"label": "Google Search Console", "freshnessDays": 1, "estimatedCallsPerRun": 3},
    "ga4": {"label": "Google Analytics 4", "freshnessDays": 1, "estimatedCallsPerRun": 1},
    "pagespeed": {"label": "PageSpeed Insights", "freshnessDays": 7, "estimatedCallsPerRun": 1},
    "crux": {"label": "Chrome UX Report", "freshnessDays": 30, "estimatedCallsPerRun": 1},
}


def overview() -> dict[str, Any]:
    cfg = settings()
    cloud_status = cloud.health()
    cloud_ok = bool(cloud_status.get("ok"))
    table_counts = cloud_status.get("tableCounts", {}) if cloud_ok else {}
    cloud_runs: list[dict[str, Any]] = []
    cloud_quota: list[dict[str, Any]] = []
    if cloud_ok:
        try:
            cloud_runs = cloud.recent_api_runs(30)
            cloud_quota = normalize_cloud_quota(cloud.quota_source_status(30))
        except Exception:  # noqa: BLE001
            cloud_runs = []
            cloud_quota = []

    local = local_backup.status()
    local_runs = local_backup.recent_runs(30)
    local_quota = local_backup.quota_sources(30)

    return {
        "architecture": architecture(),
        "database": {
            "mode": cfg.database_mode,
            "primary": "local_raw_exports_and_sqlite",
            "cloudReplica": "supabase_postgres",
            "localBackup": "backup_manifests_and_raw_snapshots",
            "cloudDegraded": not cloud_ok,
            "cloudMessage": "" if cloud_ok else str(cloud_status.get("message") or "Cloud database is unavailable."),
        },
        "cloud": {
            **cloud_status,
            "tableCounts": table_counts or cloud_status.get("tableCounts", {}),
            "recentRuns": cloud_runs,
            "quotaSources": cloud_quota,
        },
        "localBackup": local,
        "recentRuns": local_runs,
        "quota": {
            "sources": local_quota,
            "source": "local_sqlite",
            "rules": {
                "gsc": "Refresh daily unless forced.",
                "ga4": "Refresh daily unless forced.",
                "pagespeed": "Refresh when a URL is new, stale after 7 days, changed, or forced.",
                "crux": "Refresh monthly or after meaningful traffic growth.",
            },
        },
    }


def architecture() -> dict[str, Any]:
    return {
        "mode": "modern_web_app_local_first",
        "frontend": "React + TypeScript + Vite",
        "backend": "FastAPI service layer",
        "sourceOfTruth": "Local raw API exports and SQLite",
        "cloudReplica": "Supabase Postgres",
        "backupPolicy": "Local upload snapshots and backup manifests",
        "legacyCompatibility": "apps/seo_dashboard remains available during migration",
    }


def normalize_cloud_quota(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_source = {str(row.get("source")): row for row in rows}
    result = []
    for source, policy in POLICIES.items():
        row = by_source.get(source, {})
        latest_success = row.get("latest_success_at")
        freshness = freshness_status(latest_success, int(policy["freshnessDays"]))
        today_runs = int(row.get("today_runs") or 0)
        result.append(
            {
                "source": source,
                "label": policy["label"],
                "totalRuns": int(row.get("total_runs") or 0),
                "okCount": int(row.get("ok_count") or 0),
                "errorCount": int(row.get("error_count") or 0),
                "todayRuns": today_runs,
                "estimatedCallsToday": today_runs * int(policy["estimatedCallsPerRun"]),
                "latestAt": str(row.get("latest_at") or ""),
                "latestSuccessAt": str(latest_success or ""),
                "latestErrorAt": str(row.get("latest_error_at") or ""),
                **freshness,
            }
        )
    return result


def freshness_status(latest_success: object, freshness_days: int) -> dict[str, Any]:
    if not latest_success:
        return {"ageDays": None, "freshness": "missing", "recommendation": "Run sync before analysis."}
    if isinstance(latest_success, dt.datetime):
        latest = latest_success.replace(tzinfo=None)
    else:
        try:
            latest = dt.datetime.fromisoformat(str(latest_success).replace("Z", "+00:00")).replace(tzinfo=None)
        except ValueError:
            return {"ageDays": None, "freshness": "unknown", "recommendation": "Check latest sync timestamp."}
    age_days = max((dt.datetime.now() - latest).days, 0)
    if age_days > freshness_days:
        return {"ageDays": age_days, "freshness": "stale", "recommendation": f"Refresh; target cadence is {freshness_days} day(s)."}
    return {"ageDays": age_days, "freshness": "fresh", "recommendation": "Use cloud data unless a force refresh is needed."}
