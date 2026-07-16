"""Latest-only PageSpeed persistence.

The active identity is ``(normalized requested URL, strategy)``.  Successful
results own one SQLite row and one deterministic raw file.  Attempt evidence is
kept separately and never contains historical scores, audits, or payloads.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import sqlite3
from typing import Any


ROOT = Path(__file__).resolve().parents[3]
DB_PATH = ROOT / "data" / "local" / "seo_dashboard.sqlite"
RAW_DIR = ROOT / "data" / "pagespeed" / "raw"
SCHEMA_VERSION = "pagespeed-latest-v1"


def connect(db_path: Path | None = None) -> sqlite3.Connection:
    path = db_path or DB_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    init_schema(conn)
    return conn


def init_schema(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS pagespeed_latest_results (
            url_key TEXT NOT NULL,
            strategy TEXT NOT NULL CHECK (strategy IN ('mobile', 'desktop')),
            requested_url TEXT NOT NULL,
            final_url TEXT,
            fetched_at TEXT,
            saved_at TEXT NOT NULL,
            lighthouse_version TEXT,
            locale TEXT,
            result_json TEXT NOT NULL,
            raw_path TEXT NOT NULL,
            PRIMARY KEY (url_key, strategy)
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS pagespeed_latest_attempts (
            url_key TEXT NOT NULL,
            strategy TEXT NOT NULL CHECK (strategy IN ('mobile', 'desktop')),
            requested_url TEXT NOT NULL,
            status TEXT NOT NULL,
            error_code TEXT,
            error_message TEXT,
            http_status INTEGER,
            started_at TEXT NOT NULL,
            completed_at TEXT,
            duration_ms INTEGER,
            persistence_status TEXT,
            cloud_status_json TEXT,
            PRIMARY KEY (url_key, strategy)
        )
        """
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_pagespeed_latest_saved ON pagespeed_latest_results(saved_at DESC)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_pagespeed_attempt_status ON pagespeed_latest_attempts(status, completed_at DESC)")
    conn.commit()


def active_file_path(url_key: str, strategy: str, raw_dir: Path | None = None) -> Path:
    digest = hashlib.sha256(url_key.encode("utf-8")).hexdigest()[:32]
    return (raw_dir or RAW_DIR) / f"pagespeed_active_{digest}_{strategy}.json"


def _relative(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(ROOT)).replace("\\", "/")
    except ValueError:
        return path.name


def persist_success(
    result: dict[str, Any],
    response: dict[str, Any],
    *,
    db_path: Path | None = None,
    raw_dir: Path | None = None,
) -> dict[str, Any]:
    """Atomically replace the active raw file and unique latest SQLite row."""

    directory = raw_dir or RAW_DIR
    directory.mkdir(parents=True, exist_ok=True)
    target = active_file_path(str(result["urlKey"]), str(result["strategy"]), directory)
    now = dt.datetime.now(dt.timezone.utc).isoformat()
    stored_result = {**result, "schemaVersion": SCHEMA_VERSION, "status": "success", "savedAt": now}
    wrapper = {"schemaVersion": SCHEMA_VERSION, "result": stored_result, "response": response}
    encoded = json.dumps(wrapper, ensure_ascii=False, separators=(",", ":"))
    # Validate the exact bytes before the transactional replacement begins.
    json.loads(encoded)
    temp = target.with_suffix(target.suffix + f".{os.getpid()}.tmp")
    backup = target.with_suffix(target.suffix + f".{os.getpid()}.bak")
    temp.write_text(encoded, encoding="utf-8")
    conn = connect(db_path)
    moved_old = False
    try:
        conn.execute("BEGIN IMMEDIATE")
        stored_result["rawReference"] = _relative(target)
        conn.execute(
            """
            INSERT INTO pagespeed_latest_results (
                url_key, strategy, requested_url, final_url, fetched_at, saved_at,
                lighthouse_version, locale, result_json, raw_path
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(url_key, strategy) DO UPDATE SET
                requested_url = excluded.requested_url,
                final_url = excluded.final_url,
                fetched_at = excluded.fetched_at,
                saved_at = excluded.saved_at,
                lighthouse_version = excluded.lighthouse_version,
                locale = excluded.locale,
                result_json = excluded.result_json,
                raw_path = excluded.raw_path
            """,
            (
                stored_result["urlKey"],
                stored_result["strategy"],
                stored_result["requestedUrl"],
                stored_result.get("finalUrl"),
                stored_result.get("fetchTime"),
                now,
                stored_result.get("lighthouseVersion"),
                stored_result.get("locale"),
                json.dumps(stored_result, ensure_ascii=False, separators=(",", ":")),
                _relative(target),
            ),
        )
        if target.exists():
            os.replace(target, backup)
            moved_old = True
        os.replace(temp, target)
        conn.commit()
        if backup.exists():
            backup.unlink()
        return stored_result
    except Exception:
        conn.rollback()
        if target.exists() and moved_old:
            target.unlink()
        if backup.exists():
            os.replace(backup, target)
        raise
    finally:
        conn.close()
        if temp.exists():
            temp.unlink()
        if backup.exists() and not target.exists():
            os.replace(backup, target)


def record_attempt(
    *,
    url_key: str,
    requested_url: str,
    strategy: str,
    status: str,
    started_at: str,
    completed_at: str | None = None,
    duration_ms: int | None = None,
    error_code: str = "",
    error_message: str = "",
    http_status: int | None = None,
    persistence_status: str = "",
    cloud_status: dict[str, Any] | None = None,
    db_path: Path | None = None,
) -> None:
    with connect(db_path) as conn:
        conn.execute(
            """
            INSERT INTO pagespeed_latest_attempts (
                url_key, strategy, requested_url, status, error_code, error_message,
                http_status, started_at, completed_at, duration_ms,
                persistence_status, cloud_status_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(url_key, strategy) DO UPDATE SET
                requested_url = excluded.requested_url,
                status = excluded.status,
                error_code = excluded.error_code,
                error_message = excluded.error_message,
                http_status = excluded.http_status,
                started_at = excluded.started_at,
                completed_at = excluded.completed_at,
                duration_ms = excluded.duration_ms,
                persistence_status = excluded.persistence_status,
                cloud_status_json = excluded.cloud_status_json
            """,
            (
                url_key,
                strategy,
                requested_url,
                status,
                error_code,
                error_message[:500],
                http_status,
                started_at,
                completed_at,
                duration_ms,
                persistence_status,
                json.dumps(cloud_status or {}, ensure_ascii=False, separators=(",", ":")),
            ),
        )
        conn.commit()


def update_result_persistence(url_key: str, strategy: str, persistence: dict[str, Any], *, db_path: Path | None = None) -> None:
    with connect(db_path) as conn:
        row = conn.execute("SELECT result_json FROM pagespeed_latest_results WHERE url_key = ? AND strategy = ?", (url_key, strategy)).fetchone()
        if not row:
            return
        try:
            result = json.loads(row["result_json"])
        except (TypeError, json.JSONDecodeError):
            return
        result["persistence"] = persistence
        conn.execute(
            "UPDATE pagespeed_latest_results SET result_json = ? WHERE url_key = ? AND strategy = ?",
            (json.dumps(result, ensure_ascii=False, separators=(",", ":")), url_key, strategy),
        )
        conn.commit()


def _row_result(row: sqlite3.Row) -> dict[str, Any]:
    try:
        result = json.loads(row["result_json"])
    except (TypeError, json.JSONDecodeError):
        result = {}
    result["rawReference"] = row["raw_path"]
    return result


def latest_results(
    url_key: str = "",
    strategy: str = "",
    *,
    db_path: Path | None = None,
) -> list[dict[str, Any]]:
    clauses: list[str] = []
    values: list[Any] = []
    if url_key:
        clauses.append("r.url_key = ?")
        values.append(url_key)
    if strategy:
        clauses.append("r.strategy = ?")
        values.append(strategy)
    where = " WHERE " + " AND ".join(clauses) if clauses else ""
    with connect(db_path) as conn:
        rows = conn.execute(
            f"""
            SELECT r.*, a.status AS attempt_status, a.error_code AS attempt_error_code,
                   a.error_message AS attempt_error_message, a.http_status AS attempt_http_status,
                   a.started_at AS attempt_started_at, a.completed_at AS attempt_completed_at,
                   a.duration_ms AS attempt_duration_ms, a.persistence_status AS attempt_persistence_status,
                   a.cloud_status_json AS attempt_cloud_status_json
            FROM pagespeed_latest_results r
            LEFT JOIN pagespeed_latest_attempts a
              ON a.url_key = r.url_key AND a.strategy = r.strategy
            {where}
            ORDER BY r.saved_at DESC, r.strategy
            """,
            values,
        ).fetchall()
        attempts_without_success = conn.execute(
            f"""
            SELECT a.* FROM pagespeed_latest_attempts a
            LEFT JOIN pagespeed_latest_results r
              ON r.url_key = a.url_key AND r.strategy = a.strategy
            WHERE r.url_key IS NULL
              {('AND a.url_key = ?' if url_key else '')}
              {('AND a.strategy = ?' if strategy else '')}
            ORDER BY a.completed_at DESC
            """,
            ([url_key] if url_key else []) + ([strategy] if strategy else []),
        ).fetchall()
    results = []
    for row in rows:
        item = _row_result(row)
        try:
            cloud = json.loads(row["attempt_cloud_status_json"] or "{}")
        except json.JSONDecodeError:
            cloud = {}
        item["latestAttempt"] = {
            "status": row["attempt_status"] or "success",
            "errorCode": row["attempt_error_code"] or "",
            "message": row["attempt_error_message"] or "",
            "httpStatus": row["attempt_http_status"],
            "startedAt": row["attempt_started_at"],
            "completedAt": row["attempt_completed_at"],
            "durationMs": row["attempt_duration_ms"],
            "persistenceStatus": row["attempt_persistence_status"] or "saved",
            "cloud": cloud,
        }
        results.append(item)
    for row in attempts_without_success:
        try:
            cloud = json.loads(row["cloud_status_json"] or "{}")
        except json.JSONDecodeError:
            cloud = {}
        results.append(
            {
                "schemaVersion": SCHEMA_VERSION,
                "status": "no_success",
                "urlKey": row["url_key"],
                "requestedUrl": row["requested_url"],
                "strategy": row["strategy"],
                "latestAttempt": {
                    "status": row["status"],
                    "errorCode": row["error_code"] or "",
                    "message": row["error_message"] or "",
                    "httpStatus": row["http_status"],
                    "startedAt": row["started_at"],
                    "completedAt": row["completed_at"],
                    "durationMs": row["duration_ms"],
                    "persistenceStatus": row["persistence_status"] or "",
                    "cloud": cloud,
                },
            }
        )
    return results


def read_raw(url_key: str, strategy: str, *, raw_dir: Path | None = None) -> dict[str, Any] | None:
    path = active_file_path(url_key, strategy, raw_dir)
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return data if isinstance(data, dict) else None


def counts(*, db_path: Path | None = None, raw_dir: Path | None = None) -> dict[str, int]:
    with connect(db_path) as conn:
        rows = int(conn.execute("SELECT COUNT(*) FROM pagespeed_latest_results").fetchone()[0])
        attempts = int(conn.execute("SELECT COUNT(*) FROM pagespeed_latest_attempts").fetchone()[0])
    directory = raw_dir or RAW_DIR
    files = len(list(directory.glob("pagespeed_active_*_mobile.json"))) + len(list(directory.glob("pagespeed_active_*_desktop.json"))) if directory.exists() else 0
    return {"activeRows": rows, "activeRawFiles": files, "latestAttempts": attempts}


def clear_legacy_rows(*, db_path: Path | None = None) -> int:
    with connect(db_path) as conn:
        exists = conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='pagespeed_runs'").fetchone()
        if not exists:
            return 0
        count = int(conn.execute("SELECT COUNT(*) FROM pagespeed_runs").fetchone()[0])
        conn.execute("DELETE FROM pagespeed_runs")
        conn.commit()
        return count
