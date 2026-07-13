#!/usr/bin/env python3
"""SQLite local storage for API sync status and summaries."""

from __future__ import annotations

import datetime as dt
import json
from pathlib import Path
import sqlite3
from typing import Any


ROOT = Path(__file__).resolve().parents[3]
DB_PATH = ROOT / "data" / "local" / "seo_dashboard.sqlite"
API_POLICIES = {
    "gsc": {"label": "Google Search Console", "freshnessDays": 1, "estimatedCallsPerRun": 3},
    "ga4": {"label": "Google Analytics 4", "freshnessDays": 1, "estimatedCallsPerRun": 1},
    "pagespeed": {"label": "PageSpeed Insights", "freshnessDays": 7, "estimatedCallsPerRun": 1},
    "crux": {"label": "Chrome UX Report", "freshnessDays": 30, "estimatedCallsPerRun": 1},
}


def connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    init_db(conn)
    return conn


def init_db(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS api_runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source TEXT NOT NULL,
            status TEXT NOT NULL,
            command TEXT,
            summary_json TEXT,
            raw_path TEXT,
            error TEXT,
            created_at TEXT NOT NULL
        )
        """
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_api_runs_source_time ON api_runs(source, created_at DESC)")
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS pagespeed_runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            url TEXT NOT NULL,
            final_url TEXT,
            strategy TEXT,
            fetched_at TEXT,
            performance REAL,
            accessibility REAL,
            best_practices REAL,
            seo REAL,
            lcp TEXT,
            tbt TEXT,
            cls TEXT,
            speed_index TEXT,
            raw_path TEXT,
            created_at TEXT NOT NULL
        )
        """
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_pagespeed_runs_url_time ON pagespeed_runs(url, fetched_at DESC, created_at DESC)")
    conn.commit()


def record_api_run(
    source: str,
    status: str,
    command: str = "",
    summary: dict[str, Any] | None = None,
    raw_path: str = "",
    error: str = "",
) -> int:
    with connect() as conn:
        cursor = conn.execute(
            """
            INSERT INTO api_runs (source, status, command, summary_json, raw_path, error, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                source,
                status,
                command,
                json.dumps(summary or {}, ensure_ascii=False),
                raw_path,
                error,
                dt.datetime.now().isoformat(timespec="seconds"),
            ),
        )
        conn.commit()
        return int(cursor.lastrowid)


def update_api_run_summary(run_id: int, summary: dict[str, Any]) -> None:
    with connect() as conn:
        conn.execute(
            "UPDATE api_runs SET summary_json = ? WHERE id = ?",
            (json.dumps(summary, ensure_ascii=False), run_id),
        )
        conn.commit()


def latest_api_run(source: str) -> dict[str, Any] | None:
    with connect() as conn:
        row = conn.execute(
            "SELECT * FROM api_runs WHERE source = ? ORDER BY created_at DESC, id DESC LIMIT 1",
            (source,),
        ).fetchone()
    if not row:
        return None
    return row_to_dict(row)


def recent_api_runs(limit: int = 20) -> list[dict[str, Any]]:
    with connect() as conn:
        rows = conn.execute(
            "SELECT * FROM api_runs ORDER BY created_at DESC, id DESC LIMIT ?",
            (limit,),
        ).fetchall()
    return [row_to_dict(row) for row in rows]


def api_run_summary(days: int = 7) -> dict[str, Any]:
    since = (dt.datetime.now() - dt.timedelta(days=days)).isoformat(timespec="seconds")
    today = dt.date.today().isoformat()
    with connect() as conn:
        by_source = conn.execute(
            """
            SELECT source,
                   COUNT(*) AS total,
                   SUM(CASE WHEN status = 'ok' THEN 1 ELSE 0 END) AS ok_count,
                   SUM(CASE WHEN status != 'ok' THEN 1 ELSE 0 END) AS error_count,
                   MAX(created_at) AS latest_at
            FROM api_runs
            WHERE created_at >= ?
            GROUP BY source
            ORDER BY source
            """,
            (since,),
        ).fetchall()
        today_rows = conn.execute(
            """
            SELECT source, COUNT(*) AS total
            FROM api_runs
            WHERE substr(created_at, 1, 10) = ?
            GROUP BY source
            ORDER BY source
            """,
            (today,),
        ).fetchall()
        total = conn.execute("SELECT COUNT(*) AS total FROM api_runs").fetchone()
    return {
        "days": days,
        "totalRuns": int(total["total"] if total else 0),
        "bySource": [dict(row) for row in by_source],
        "today": [dict(row) for row in today_rows],
    }


def api_source_status(days: int = 30) -> list[dict[str, Any]]:
    since = (dt.datetime.now() - dt.timedelta(days=days)).isoformat(timespec="seconds")
    today = dt.date.today().isoformat()
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT *
            FROM api_runs
            WHERE created_at >= ?
            ORDER BY source, created_at DESC, id DESC
            """,
            (since,),
        ).fetchall()
    grouped: dict[str, list[dict[str, Any]]] = {source: [] for source in API_POLICIES}
    for row in rows:
        item = row_to_dict(row)
        grouped.setdefault(str(item.get("source") or "unknown"), []).append(item)

    result = []
    for source, source_rows in sorted(grouped.items()):
        policy = API_POLICIES.get(source, {"label": source, "freshnessDays": 7, "estimatedCallsPerRun": 1})
        ok_rows = [row for row in source_rows if row.get("status") == "ok"]
        error_rows = [row for row in source_rows if row.get("status") != "ok"]
        today_count = sum(1 for row in source_rows if str(row.get("created_at", "")).startswith(today))
        latest = source_rows[0] if source_rows else None
        latest_ok = ok_rows[0] if ok_rows else None
        latest_error = error_rows[0] if error_rows else None
        freshness = freshness_status(str(latest_ok.get("created_at", "")) if latest_ok else "", int(policy["freshnessDays"]))
        result.append(
            {
                "source": source,
                "label": policy["label"],
                "totalRuns": len(source_rows),
                "okCount": len(ok_rows),
                "errorCount": len(error_rows),
                "todayRuns": today_count,
                "estimatedCallsToday": today_count * int(policy["estimatedCallsPerRun"]),
                "freshnessDays": policy["freshnessDays"],
                "estimatedCallsPerRun": policy["estimatedCallsPerRun"],
                "latestAt": latest.get("created_at", "") if latest else "",
                "latestStatus": latest.get("status", "") if latest else "never",
                "latestSuccessAt": latest_ok.get("created_at", "") if latest_ok else "",
                "latestErrorAt": latest_error.get("created_at", "") if latest_error else "",
                "latestError": str(latest_error.get("error", ""))[:240] if latest_error else "",
                **freshness,
            }
        )
    return result


def freshness_status(latest_success_at: str, freshness_days: int) -> dict[str, Any]:
    if not latest_success_at:
        return {"ageDays": None, "freshness": "missing", "recommendation": "Run sync before analysis."}
    try:
        latest = dt.datetime.fromisoformat(latest_success_at)
    except ValueError:
        return {"ageDays": None, "freshness": "unknown", "recommendation": "Check latest sync timestamp."}
    age_days = max((dt.datetime.now() - latest).days, 0)
    if age_days > freshness_days:
        return {"ageDays": age_days, "freshness": "stale", "recommendation": f"Refresh; target cadence is {freshness_days} day(s)."}
    return {"ageDays": age_days, "freshness": "fresh", "recommendation": "Use cached data unless a force refresh is needed."}


def record_pagespeed_run(summary: dict[str, Any], raw_path: str = "", strategy: str = "") -> None:
    scores = summary.get("scores", {}) if isinstance(summary.get("scores"), dict) else {}
    metrics = summary.get("coreMetrics", {}) if isinstance(summary.get("coreMetrics"), dict) else {}
    with connect() as conn:
        conn.execute(
            """
            INSERT INTO pagespeed_runs (
                url, final_url, strategy, fetched_at, performance, accessibility,
                best_practices, seo, lcp, tbt, cls, speed_index, raw_path, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                str(summary.get("requestedUrl") or ""),
                str(summary.get("finalUrl") or ""),
                strategy,
                str(summary.get("fetchTime") or ""),
                float(scores.get("performance") or 0),
                float(scores.get("accessibility") or 0),
                float(scores.get("best-practices") or 0),
                float(scores.get("seo") or 0),
                str(metrics.get("largest-contentful-paint") or ""),
                str(metrics.get("total-blocking-time") or ""),
                str(metrics.get("cumulative-layout-shift") or ""),
                str(metrics.get("speed-index") or ""),
                raw_path,
                dt.datetime.now().isoformat(timespec="seconds"),
            ),
        )
        conn.commit()


def recent_pagespeed_runs(limit: int = 100, url: str = "") -> list[dict[str, Any]]:
    with connect() as conn:
        if url:
            rows = conn.execute(
                "SELECT * FROM pagespeed_runs WHERE url = ? ORDER BY fetched_at DESC, created_at DESC, id DESC LIMIT ?",
                (url, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM pagespeed_runs ORDER BY fetched_at DESC, created_at DESC, id DESC LIMIT ?",
                (limit,),
            ).fetchall()
    return [dict(row) for row in rows]


def row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
    item = dict(row)
    try:
        item["summary"] = json.loads(item.pop("summary_json") or "{}")
    except json.JSONDecodeError:
        item["summary"] = {}
    return item
