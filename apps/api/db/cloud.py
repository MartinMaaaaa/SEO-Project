from __future__ import annotations

import contextlib
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[3]
from apps.api.db import cloud_sync


TABLES = [
    "seo_raw_files",
    "gsc_performance_rows",
    "ga4_report_rows",
    "pagespeed_report_runs",
    "crux_report_runs",
    "seo_api_runs",
    "local_backup_manifests",
]


class CloudUnavailable(RuntimeError):
    """Raised when the configured cloud database cannot be reached."""


def configured() -> bool:
    return cloud_sync.is_supabase_configured()


def health() -> dict[str, Any]:
    return cloud_sync.cloud_status()


@contextlib.contextmanager
def connection():
    if not configured():
        raise CloudUnavailable("Supabase is not configured.")
    conn = None
    try:
        conn = cloud_sync.connect()
        cloud_sync.init_schema(conn)
        yield conn
    except Exception as exc:  # noqa: BLE001
        if conn:
            try:
                conn.rollback()
            except Exception:
                pass
        raise CloudUnavailable(str(exc)[:500]) from exc
    finally:
        if conn:
            try:
                conn.close()
            except Exception:
                pass


def table_counts() -> dict[str, int]:
    with connection() as conn:
        cursor = conn.cursor()
        counts: dict[str, int] = {}
        for table in TABLES:
            cursor.execute(f"SELECT COUNT(*) FROM {table}")
            counts[table] = int(cursor.fetchone()[0])
        return counts


def recent_api_runs(limit: int = 30) -> list[dict[str, Any]]:
    with connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT source, status, command, summary, raw_path, error, created_at, uploaded_at
            FROM seo_api_runs
            ORDER BY created_at DESC NULLS LAST, uploaded_at DESC
            LIMIT %s
            """,
            (limit,),
        )
        columns = [col[0] for col in cursor.description]
        return [dict(zip(columns, row)) for row in cursor.fetchall()]


def quota_source_status(days: int = 30) -> list[dict[str, Any]]:
    with connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            WITH recent AS (
                SELECT *
                FROM seo_api_runs
                WHERE created_at >= NOW() - (%s || ' days')::interval
            )
            SELECT
                source,
                COUNT(*) AS total_runs,
                SUM(CASE WHEN status = 'ok' THEN 1 ELSE 0 END) AS ok_count,
                SUM(CASE WHEN status <> 'ok' THEN 1 ELSE 0 END) AS error_count,
                SUM(CASE WHEN created_at::date = CURRENT_DATE THEN 1 ELSE 0 END) AS today_runs,
                MAX(created_at) AS latest_at,
                MAX(CASE WHEN status = 'ok' THEN created_at ELSE NULL END) AS latest_success_at,
                MAX(CASE WHEN status <> 'ok' THEN created_at ELSE NULL END) AS latest_error_at
            FROM recent
            GROUP BY source
            ORDER BY source
            """,
            (days,),
        )
        columns = [col[0] for col in cursor.description]
        return [dict(zip(columns, row)) for row in cursor.fetchall()]


def latest_backups(limit: int = 10) -> list[dict[str, Any]]:
    with connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT backup_id, label, backup_path, manifest, created_at
            FROM local_backup_manifests
            ORDER BY created_at DESC
            LIMIT %s
            """,
            (limit,),
        )
        columns = [col[0] for col in cursor.description]
        return [dict(zip(columns, row)) for row in cursor.fetchall()]
