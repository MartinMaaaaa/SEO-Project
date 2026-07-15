"""Normalized, idempotent SQLite storage for GSC dimension exports."""

from __future__ import annotations

import datetime as dt
import json
from pathlib import Path
import sqlite3
from typing import Any, Iterable

from apps.api.core.config import ROOT
from apps.api.db.local_store import DB_PATH


TIMEZONE = "America/Los_Angeles (GSC reporting)"
DIMENSION_COLUMNS = {
    "date": "date",
    "query": "query",
    "page": "page",
    "country": "country",
    "device": "device",
    "searchAppearance": "search_appearance",
}
SUPPORTED_BREAKDOWNS = {
    "country": ("date", "country"),
    "device": ("date", "device"),
    "searchAppearance": ("date", "searchAppearance"),
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
        CREATE TABLE IF NOT EXISTS gsc_exports (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            scope_key TEXT NOT NULL UNIQUE,
            site_property TEXT NOT NULL,
            search_type TEXT NOT NULL,
            data_state TEXT NOT NULL,
            start_date TEXT NOT NULL,
            end_date TEXT NOT NULL,
            dimensions_key TEXT NOT NULL,
            requested_dimensions_json TEXT NOT NULL,
            filters_json TEXT NOT NULL,
            aggregation_type TEXT,
            response_aggregation_type TEXT,
            row_limit INTEGER NOT NULL,
            start_row INTEGER NOT NULL,
            row_count INTEGER NOT NULL,
            row_limit_reached INTEGER NOT NULL DEFAULT 0,
            source_file TEXT NOT NULL,
            source_run_id INTEGER,
            extracted_at TEXT NOT NULL,
            imported_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_gsc_exports_grain_range
            ON gsc_exports(dimensions_key, start_date, end_date, extracted_at DESC);

        CREATE TABLE IF NOT EXISTS gsc_dimension_rows (
            export_id INTEGER NOT NULL REFERENCES gsc_exports(id) ON DELETE CASCADE,
            row_index INTEGER NOT NULL,
            date TEXT,
            query TEXT,
            page TEXT,
            country TEXT,
            device TEXT,
            search_appearance TEXT,
            clicks REAL NOT NULL DEFAULT 0,
            impressions REAL NOT NULL DEFAULT 0,
            ctr REAL NOT NULL DEFAULT 0,
            position REAL NOT NULL DEFAULT 0,
            PRIMARY KEY (export_id, row_index)
        );
        CREATE INDEX IF NOT EXISTS idx_gsc_dimension_rows_date
            ON gsc_dimension_rows(date);
        CREATE INDEX IF NOT EXISTS idx_gsc_dimension_rows_country
            ON gsc_dimension_rows(country);
        CREATE INDEX IF NOT EXISTS idx_gsc_dimension_rows_device
            ON gsc_dimension_rows(device);
        CREATE INDEX IF NOT EXISTS idx_gsc_dimension_rows_appearance
            ON gsc_dimension_rows(search_appearance);
        """
    )
    conn.commit()


def _number(value: Any) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def _relative(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(ROOT)).replace("\\", "/")
    except ValueError:
        return str(path.resolve()).replace("\\", "/")


def _materialized_dimensions(request: dict[str, Any]) -> tuple[list[str], dict[str, str]]:
    requested = [str(item) for item in request.get("dimensions", [])]
    fixed: dict[str, str] = {}
    groups = request.get("dimensionFilterGroups", [])
    for group in groups if isinstance(groups, list) else []:
        for item in group.get("filters", []) if isinstance(group, dict) else []:
            dimension = str(item.get("dimension", ""))
            if dimension == "searchAppearance" and str(item.get("operator", "equals")) == "equals":
                fixed[dimension] = str(item.get("expression", ""))
    materialized = list(requested)
    for dimension in fixed:
        if dimension not in materialized:
            materialized.append(dimension)
    return materialized, fixed


def import_export(path: Path, db_path: Path = DB_PATH, source_run_id: int | None = None) -> dict[str, Any]:
    """Import one saved GSC JSON export, replacing the same request scope atomically."""
    payload = json.loads(path.read_text(encoding="utf-8"))
    request = payload.get("request", {})
    response = payload.get("response", {})
    if not isinstance(request, dict) or not isinstance(response, dict):
        raise ValueError("GSC export must contain request and response objects")
    requested_dimensions = [str(item) for item in request.get("dimensions", [])]
    materialized_dimensions, fixed_dimensions = _materialized_dimensions(request)
    unknown = [item for item in materialized_dimensions if item not in DIMENSION_COLUMNS]
    if unknown:
        raise ValueError(f"Unsupported GSC dimensions: {', '.join(unknown)}")
    dimensions_key = "+".join(materialized_dimensions) or "summary"
    site_property = str(payload.get("siteUrl") or "Unknown")
    search_type = str(request.get("type") or "web")
    data_state = str(request.get("dataState") or "final")
    start_date = str(request.get("startDate") or "")
    end_date = str(request.get("endDate") or "")
    row_limit = int(request.get("rowLimit") or 1000)
    start_row = int(request.get("startRow") or 0)
    filters = request.get("dimensionFilterGroups", [])
    scope_key = "|".join(
        [site_property, search_type, data_state, start_date, end_date, dimensions_key, json.dumps(filters, ensure_ascii=False, sort_keys=True), str(start_row)]
    )
    rows = response.get("rows", []) if isinstance(response.get("rows", []), list) else []
    extracted_at = dt.datetime.fromtimestamp(path.stat().st_mtime).isoformat(timespec="seconds")
    imported_at = dt.datetime.now().isoformat(timespec="seconds")
    with connect(db_path) as conn:
        conn.execute(
            """
            INSERT INTO gsc_exports (
                scope_key, site_property, search_type, data_state, start_date, end_date,
                dimensions_key, requested_dimensions_json, filters_json, aggregation_type,
                response_aggregation_type, row_limit, start_row, row_count, row_limit_reached,
                source_file, source_run_id, extracted_at, imported_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(scope_key) DO UPDATE SET
                aggregation_type=excluded.aggregation_type,
                response_aggregation_type=excluded.response_aggregation_type,
                row_limit=excluded.row_limit,
                row_count=excluded.row_count,
                row_limit_reached=excluded.row_limit_reached,
                source_file=excluded.source_file,
                source_run_id=excluded.source_run_id,
                extracted_at=excluded.extracted_at,
                imported_at=excluded.imported_at
            """,
            (
                scope_key, site_property, search_type, data_state, start_date, end_date,
                dimensions_key, json.dumps(requested_dimensions, ensure_ascii=False),
                json.dumps(filters, ensure_ascii=False, sort_keys=True),
                str(request.get("aggregationType") or "auto"),
                str(response.get("responseAggregationType") or ""), row_limit, start_row,
                len(rows), int(len(rows) >= row_limit), _relative(path), source_run_id,
                extracted_at, imported_at,
            ),
        )
        export_id = int(conn.execute("SELECT id FROM gsc_exports WHERE scope_key = ?", (scope_key,)).fetchone()["id"])
        conn.execute("DELETE FROM gsc_dimension_rows WHERE export_id = ?", (export_id,))
        inserts = []
        for index, row in enumerate(rows):
            values = {name: "" for name in DIMENSION_COLUMNS}
            keys = row.get("keys", []) if isinstance(row, dict) else []
            for position, dimension in enumerate(requested_dimensions):
                values[dimension] = str(keys[position]) if position < len(keys) else ""
            values.update(fixed_dimensions)
            inserts.append(
                (
                    export_id, index, values["date"] or None, values["query"] or None,
                    values["page"] or None, values["country"] or None, values["device"] or None,
                    values["searchAppearance"] or None, _number(row.get("clicks")),
                    _number(row.get("impressions")), _number(row.get("ctr")), _number(row.get("position")),
                )
            )
        conn.executemany(
            """
            INSERT INTO gsc_dimension_rows (
                export_id, row_index, date, query, page, country, device,
                search_appearance, clicks, impressions, ctr, position
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            inserts,
        )
        conn.commit()
    return {"exportId": export_id, "dimensions": materialized_dimensions, "rows": len(rows), "replacedScope": scope_key}


def import_exports(paths: Iterable[Path], db_path: Path = DB_PATH, source_run_id: int | None = None) -> list[dict[str, Any]]:
    return [import_export(path, db_path, source_run_id) for path in paths if path.suffix.casefold() == ".json"]


def _metrics(rows: list[dict[str, Any]]) -> dict[str, float]:
    clicks = sum(_number(row.get("clicks")) for row in rows)
    impressions = sum(_number(row.get("impressions")) for row in rows)
    weighted_position = sum(_number(row.get("position")) * _number(row.get("impressions")) for row in rows)
    return {
        "clicks": round(clicks, 4),
        "impressions": round(impressions, 4),
        "ctr": round(clicks / impressions, 6) if impressions else 0,
        "position": round(weighted_position / impressions, 4) if impressions else 0,
        "rows": len(rows),
    }


def _aggregate(rows: list[dict[str, Any]], column: str) -> list[dict[str, Any]]:
    groups: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        groups.setdefault(str(row.get(column) or "(not set)"), []).append(row)
    return [{"label": label, **_metrics(group)} for label, group in groups.items()]


def _latest_export(conn: sqlite3.Connection, dimensions_key: str) -> sqlite3.Row | None:
    return conn.execute(
        "SELECT * FROM gsc_exports WHERE dimensions_key = ? ORDER BY extracted_at DESC, id DESC LIMIT 1",
        (dimensions_key,),
    ).fetchone()


def dimension_breakdowns(
    start: dt.date,
    end: dt.date,
    previous_range: dict[str, str] | None,
    comparison_status: str,
    filters: list[dict[str, Any]],
    db_path: Path = DB_PATH,
) -> dict[str, Any]:
    """Return only breakdowns whose stored grain can honor the active scope exactly."""
    has_query_page_filter = any(str(item.get("field")) in {"query", "page"} for item in filters)
    tables: dict[str, list[dict[str, Any]]] = {}
    capabilities: dict[str, dict[str, Any]] = {}
    notices: list[str] = []
    with connect(db_path) as conn:
        for dimension, grain in SUPPORTED_BREAKDOWNS.items():
            dimensions_key = "+".join(grain)
            export = _latest_export(conn, dimensions_key)
            exports = []
            if export:
                if dimension == "searchAppearance":
                    exports = conn.execute(
                        """
                        SELECT * FROM gsc_exports
                        WHERE dimensions_key = ? AND start_date = ? AND end_date = ?
                        ORDER BY extracted_at DESC, id DESC
                        """,
                        (dimensions_key, str(export["start_date"]), str(export["end_date"])),
                    ).fetchall()
                else:
                    exports = [export]
            available = export is not None
            range_supported = bool(export and str(export["start_date"]) <= start.isoformat() and str(export["end_date"]) >= end.isoformat())
            enabled = available and range_supported and not has_query_page_filter
            reason = ""
            if not available:
                reason = "Requires a compatible GSC collection."
            elif not range_supported:
                reason = "The selected range is outside this dimension cache coverage."
            elif has_query_page_filter:
                reason = "This property-level grain cannot be combined with Query or Page filters."
            capabilities[dimension] = {
                "available": available,
                "enabled": enabled,
                "grain": list(grain),
                "scope": "property",
                "supportsQueryFilter": False,
                "supportsPageFilter": False,
                "reason": reason,
                "sourceFile": str(export["source_file"]) if export else None,
                "sourceFiles": [str(item["source_file"]) for item in exports],
                "cacheCoverage": {"start": str(export["start_date"]), "end": str(export["end_date"])} if export else None,
                "rowLimitReached": any(bool(item["row_limit_reached"]) for item in exports),
            }
            if not enabled or not export:
                tables[dimension] = []
                continue
            export_ids = [int(item["id"]) for item in exports]
            placeholders = ",".join("?" for _ in export_ids)
            rows = [dict(row) for row in conn.execute(
                f"SELECT * FROM gsc_dimension_rows WHERE export_id IN ({placeholders}) AND date >= ? AND date <= ?",
                (*export_ids, start.isoformat(), end.isoformat()),
            ).fetchall()]
            current = {item["label"]: item for item in _aggregate(rows, DIMENSION_COLUMNS[dimension])}
            previous: dict[str, dict[str, Any]] = {}
            if comparison_status == "complete" and previous_range:
                previous_rows = [dict(row) for row in conn.execute(
                    f"SELECT * FROM gsc_dimension_rows WHERE export_id IN ({placeholders}) AND date >= ? AND date <= ?",
                    (*export_ids, previous_range["start"], previous_range["end"]),
                ).fetchall()]
                previous = {item["label"]: item for item in _aggregate(previous_rows, DIMENSION_COLUMNS[dimension])}
            combined = []
            labels = set(current) | (set(previous) if comparison_status == "complete" else set())
            for label in labels:
                now_present, before_present = label in current, label in previous
                item = dict(current.get(label, {"label": label, "clicks": 0, "impressions": 0, "ctr": None, "position": None, "rows": 0}))
                before = previous.get(label)
                if comparison_status == "complete":
                    fallback = {"clicks": 0, "impressions": 0, "ctr": None, "position": None}
                    previous_item = before or fallback
                    for metric in ("clicks", "impressions", "ctr", "position"):
                        prior = previous_item.get(metric)
                        current_value = item.get(metric)
                        item[f"previous_{metric}"] = prior
                        if prior is None or current_value is None:
                            item[f"delta_{metric}"] = None
                            item[f"change_{metric}"] = None
                        else:
                            delta = _number(current_value) - _number(prior)
                            item[f"delta_{metric}"] = round(delta, 6)
                            item[f"change_{metric}"] = round(delta / _number(prior), 6) if _number(prior) else None
                    item["movement"] = "new" if now_present and not before_present else "lost" if before_present and not now_present else "stable"
                else:
                    item["movement"] = "comparison_unavailable"
                combined.append(item)
            tables[dimension] = sorted(combined, key=lambda item: item["clicks"], reverse=True)
            if any(bool(item["row_limit_reached"]) for item in exports):
                notices.append(f"{dimension} export reached its row limit; results may be truncated.")
    return {"tables": tables, "capabilities": capabilities, "notices": notices}


def storage_counts(db_path: Path = DB_PATH) -> dict[str, int]:
    with connect(db_path) as conn:
        exports = int(conn.execute("SELECT COUNT(*) FROM gsc_exports").fetchone()[0])
        rows = int(conn.execute("SELECT COUNT(*) FROM gsc_dimension_rows").fetchone()[0])
    return {"exports": exports, "rows": rows}
