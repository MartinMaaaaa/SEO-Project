"""Normalized, idempotent SQLite storage for GA4 Data API exports."""

from __future__ import annotations

import datetime as dt
import json
from pathlib import Path
import sqlite3
from typing import Any, Iterable

from apps.api.core.config import ROOT
from apps.api.db.local_store import DB_PATH


DIMENSION_COLUMNS = {
    "date": "date",
    "dateRange": "date_range",
    "sessionDefaultChannelGroup": "channel",
    "sessionSourceMedium": "source_medium",
    "landingPagePlusQueryString": "landing_page",
    "deviceCategory": "device",
    "country": "country",
    "eventName": "event_name",
}
METRIC_COLUMNS = {
    "sessions": "sessions",
    "totalUsers": "total_users",
    "newUsers": "new_users",
    "engagedSessions": "engaged_sessions",
    "engagementRate": "engagement_rate",
    "screenPageViews": "screen_page_views",
    "keyEvents": "key_events",
}


def connect(db_path: Path = DB_PATH) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    init_db(conn)
    return conn


def init_db(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS ga4_exports (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            scope_key TEXT NOT NULL UNIQUE,
            property_id TEXT NOT NULL,
            report_label TEXT NOT NULL,
            date_ranges_json TEXT NOT NULL,
            dimensions_key TEXT NOT NULL,
            metrics_key TEXT NOT NULL,
            filters_json TEXT NOT NULL,
            row_limit INTEGER NOT NULL,
            row_count INTEGER NOT NULL,
            row_limit_reached INTEGER NOT NULL DEFAULT 0,
            source_file TEXT NOT NULL,
            source_run_id INTEGER,
            extracted_at TEXT NOT NULL,
            imported_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_ga4_exports_label_time
            ON ga4_exports(report_label, extracted_at DESC);

        CREATE TABLE IF NOT EXISTS ga4_rows (
            export_id INTEGER NOT NULL REFERENCES ga4_exports(id) ON DELETE CASCADE,
            row_index INTEGER NOT NULL,
            date TEXT,
            date_range TEXT,
            channel TEXT,
            source_medium TEXT,
            landing_page TEXT,
            device TEXT,
            country TEXT,
            event_name TEXT,
            sessions REAL,
            total_users REAL,
            new_users REAL,
            engaged_sessions REAL,
            engagement_rate REAL,
            screen_page_views REAL,
            key_events REAL,
            PRIMARY KEY (export_id, row_index)
        );
        CREATE INDEX IF NOT EXISTS idx_ga4_rows_date ON ga4_rows(date);
        CREATE INDEX IF NOT EXISTS idx_ga4_rows_landing ON ga4_rows(landing_page);
        CREATE INDEX IF NOT EXISTS idx_ga4_rows_channel ON ga4_rows(channel);
        """
    )
    conn.commit()


def _number(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _relative(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(ROOT)).replace("\\", "/")
    except ValueError:
        return str(path.resolve()).replace("\\", "/")


def import_export(path: Path, db_path: Path = DB_PATH, source_run_id: int | None = None) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    request = payload.get("request", {})
    response = payload.get("response", {})
    if not isinstance(request, dict) or not isinstance(response, dict):
        raise ValueError("GA4 export must contain request and response objects")
    dimensions = [str(item.get("name") or "") for item in response.get("dimensionHeaders", [])]
    metrics = [str(item.get("name") or "") for item in response.get("metricHeaders", [])]
    unsupported_dimensions = [item for item in dimensions if item not in DIMENSION_COLUMNS]
    unsupported_metrics = [item for item in metrics if item not in METRIC_COLUMNS]
    if unsupported_dimensions:
        raise ValueError(f"Unsupported GA4 dimensions: {', '.join(unsupported_dimensions)}")
    if unsupported_metrics:
        raise ValueError(f"Unsupported GA4 metrics: {', '.join(unsupported_metrics)}")
    rows = response.get("rows", []) if isinstance(response.get("rows", []), list) else []
    date_ranges = request.get("dateRanges", []) if isinstance(request.get("dateRanges", []), list) else []
    filters = request.get("dimensionFilter", {})
    report_label = str(payload.get("reportLabel") or request.get("reportLabel") or "legacy")
    property_id = str(payload.get("propertyId") or "Unknown")
    dimensions_key = "+".join(dimensions) or "summary"
    metrics_key = "+".join(metrics)
    limit = int(request.get("limit") or 10000)
    scope_key = "|".join(
        [property_id, report_label, json.dumps(date_ranges, sort_keys=True), dimensions_key, metrics_key, json.dumps(filters, sort_keys=True)]
    )
    extracted_at = dt.datetime.fromtimestamp(path.stat().st_mtime).isoformat(timespec="seconds")
    imported_at = dt.datetime.now().isoformat(timespec="seconds")
    with connect(db_path) as conn:
        conn.execute(
            """
            INSERT INTO ga4_exports (
                scope_key, property_id, report_label, date_ranges_json, dimensions_key,
                metrics_key, filters_json, row_limit, row_count, row_limit_reached,
                source_file, source_run_id, extracted_at, imported_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(scope_key) DO UPDATE SET
                row_limit=excluded.row_limit,
                row_count=excluded.row_count,
                row_limit_reached=excluded.row_limit_reached,
                source_file=excluded.source_file,
                source_run_id=excluded.source_run_id,
                extracted_at=excluded.extracted_at,
                imported_at=excluded.imported_at
            """,
            (
                scope_key, property_id, report_label, json.dumps(date_ranges, ensure_ascii=False),
                dimensions_key, metrics_key, json.dumps(filters, ensure_ascii=False, sort_keys=True),
                limit, len(rows), int(len(rows) >= limit), _relative(path), source_run_id,
                extracted_at, imported_at,
            ),
        )
        export_id = int(conn.execute("SELECT id FROM ga4_exports WHERE scope_key = ?", (scope_key,)).fetchone()["id"])
        conn.execute("DELETE FROM ga4_rows WHERE export_id = ?", (export_id,))
        inserts = []
        for index, row in enumerate(rows):
            values: dict[str, Any] = {column: None for column in DIMENSION_COLUMNS.values()}
            metric_values: dict[str, Any] = {column: None for column in METRIC_COLUMNS.values()}
            for position, name in enumerate(dimensions):
                dimension_values = row.get("dimensionValues", [])
                values[DIMENSION_COLUMNS[name]] = str(dimension_values[position].get("value", "")) if position < len(dimension_values) else None
            for position, name in enumerate(metrics):
                raw_metrics = row.get("metricValues", [])
                metric_values[METRIC_COLUMNS[name]] = _number(raw_metrics[position].get("value")) if position < len(raw_metrics) else None
            inserts.append(
                (
                    export_id, index, values["date"], values["date_range"], values["channel"],
                    values["source_medium"], values["landing_page"], values["device"], values["country"],
                    values["event_name"], metric_values["sessions"], metric_values["total_users"],
                    metric_values["new_users"], metric_values["engaged_sessions"], metric_values["engagement_rate"],
                    metric_values["screen_page_views"], metric_values["key_events"],
                )
            )
        conn.executemany(
            """
            INSERT INTO ga4_rows (
                export_id, row_index, date, date_range, channel, source_medium,
                landing_page, device, country, event_name, sessions, total_users,
                new_users, engaged_sessions, engagement_rate, screen_page_views, key_events
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            inserts,
        )
        conn.commit()
    return {"exportId": export_id, "reportLabel": report_label, "rows": len(rows), "replacedScope": scope_key}


def import_exports(paths: Iterable[Path], db_path: Path = DB_PATH, source_run_id: int | None = None) -> list[dict[str, Any]]:
    return [import_export(path, db_path, source_run_id) for path in paths if path.suffix.casefold() == ".json"]


def storage_counts(db_path: Path = DB_PATH) -> dict[str, int]:
    with connect(db_path) as conn:
        exports = int(conn.execute("SELECT COUNT(*) FROM ga4_exports").fetchone()[0])
        rows = int(conn.execute("SELECT COUNT(*) FROM ga4_rows").fetchone()[0])
    return {"exports": exports, "rows": rows}
