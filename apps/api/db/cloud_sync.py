#!/usr/bin/env python3
"""Supabase sync utilities for local SEO data.

The module never prints secrets. It keeps local backups under data/backups
before uploading raw files and normalized rows to Supabase Postgres.
"""

from __future__ import annotations

import csv
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import shutil
import sqlite3
import ssl
import sys
from typing import Any
from urllib.parse import unquote, urlparse


ROOT = Path(__file__).resolve().parents[3]
ENV_PATH = ROOT / ".env"
MIGRATION_PATH = ROOT / "db" / "migrations" / "001_supabase_schema.sql"
BACKUP_ROOT = ROOT / "data" / "backups" / "supabase_uploads"
LOCAL_SQLITE = ROOT / "data" / "local" / "seo_dashboard.sqlite"
RAW_DIRS = {
    "gsc": ROOT / "data" / "gsc" / "raw",
    "ga4": ROOT / "data" / "ga4" / "raw",
    "pagespeed": ROOT / "data" / "pagespeed" / "raw",
    "crux": ROOT / "data" / "crux" / "raw",
}


def load_env() -> dict[str, str]:
    env: dict[str, str] = {}
    if ENV_PATH.exists():
        for raw_line in ENV_PATH.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            env[key.strip()] = value.strip().strip('"').strip("'")
    for key, value in os.environ.items():
        if key.startswith("SUPABASE_") or key == "DATABASE_PROVIDER":
            env[key] = value
    return env


def is_supabase_configured() -> bool:
    env = load_env()
    return bool((env.get("SUPABASE_POOLER_URL") or env.get("SUPABASE_DATABASE_URL")) and env.get("SUPABASE_SERVICE_ROLE_KEY"))


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def relative(path: Path) -> str:
    return str(path.resolve().relative_to(ROOT)).replace("\\", "/")


def source_for_path(path: Path) -> str:
    rel = relative(path)
    parts = rel.split("/")
    if len(parts) >= 3 and parts[0] == "data":
        return parts[1]
    return "local"


def safe_json_load(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def number(value: object) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def parse_date(value: str) -> str | None:
    if not value:
        return None
    value = value.strip()
    for fmt in ("%Y-%m-%d", "%Y%m%d"):
        try:
            return dt.datetime.strptime(value, fmt).date().isoformat()
        except ValueError:
            continue
    return None


def parse_timestamp(value: str) -> str | None:
    if not value:
        return None
    try:
        return dt.datetime.fromisoformat(value.replace("Z", "+00:00")).isoformat()
    except ValueError:
        return None


def metadata_from_name(path: Path) -> dict[str, Any]:
    name = path.name
    if name.startswith("gsc_"):
        stem = path.stem
        parts = stem.split("_")
        if len(parts) >= 6:
            return {
                "source": "gsc",
                "site_property": parts[1],
                "start_date": parts[2],
                "end_date": parts[3],
                "dimensions": parts[4].split("-"),
            }
    if name.startswith("ga4_"):
        stem = path.stem
        parts = stem.split("_")
        date_index = next(
            (
                index
                for index in range(2, len(parts) - 1)
                if parse_date(parts[index]) and parse_date(parts[index + 1])
            ),
            None,
        )
        if date_index is not None:
            return {
                "source": "ga4",
                "property_id": parts[1],
                "report_label": "_".join(parts[2:date_index]),
                "start_date": parts[date_index],
                "end_date": parts[date_index + 1],
                "dimensions": parts[date_index + 2].split("-") if len(parts) > date_index + 2 else [],
            }
    if name.startswith("pagespeed_"):
        strategy = ""
        if "_mobile_" in name:
            strategy = "mobile"
        elif "_desktop_" in name:
            strategy = "desktop"
        return {"source": "pagespeed", "strategy": strategy}
    if name.startswith("crux_"):
        parts = path.stem.split("_")
        return {
            "source": "crux",
            "target_type": parts[1] if len(parts) > 1 else "",
            "form_factor": parts[-2] if len(parts) > 3 else "",
        }
    return {"source": source_for_path(path)}


def connect(timeout: int = 30):
    try:
        import pg8000.dbapi
    except ImportError as exc:
        raise RuntimeError("Missing Postgres driver. Install with: python -m pip install pg8000") from exc

    env = load_env()
    url = env.get("SUPABASE_POOLER_URL") or env.get("SUPABASE_DATABASE_URL")
    if not url:
        raise RuntimeError("Missing SUPABASE_POOLER_URL or SUPABASE_DATABASE_URL")
    parsed = urlparse(url)
    if ":" in parsed.netloc.split("@")[0]:
        user_info = parsed.netloc.split("@")[0]
        user, password = user_info.split(":", 1)
    else:
        user = parsed.username or ""
        password = parsed.password or ""
    # Supabase pooler URLs commonly map to libpq sslmode=require: encrypted
    # transport without client-side CA validation. Some Windows Python bundles
    # miss the required CA chain, so use the same practical behavior here.
    ssl_context = ssl._create_unverified_context()
    conn = pg8000.dbapi.connect(
        user=unquote(user),
        password=unquote(password),
        host=parsed.hostname,
        port=parsed.port or 5432,
        database=parsed.path.lstrip("/") or "postgres",
        ssl_context=ssl_context,
        timeout=timeout,
    )
    return conn


def split_sql(sql: str) -> list[str]:
    statements: list[str] = []
    current: list[str] = []
    in_single = False
    for char in sql:
        if char == "'":
            in_single = not in_single
        if char == ";" and not in_single:
            statement = "".join(current).strip()
            if statement:
                statements.append(statement)
            current = []
        else:
            current.append(char)
    tail = "".join(current).strip()
    if tail:
        statements.append(tail)
    return statements


def init_schema(conn) -> None:
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT to_regclass('public.seo_raw_files')")
        if cursor.fetchone()[0]:
            return
    except Exception:
        conn.rollback()
    sql = MIGRATION_PATH.read_text(encoding="utf-8")
    for statement in split_sql(sql):
        cursor.execute(statement)
    conn.commit()


def make_backup(paths: list[Path], label: str) -> dict[str, Any]:
    stamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_id = f"{stamp}_{label}"
    backup_dir = BACKUP_ROOT / backup_id
    backup_dir.mkdir(parents=True, exist_ok=True)
    manifest: dict[str, Any] = {
        "backupId": backup_id,
        "label": label,
        "createdAt": dt.datetime.now().isoformat(timespec="seconds"),
        "files": [],
    }
    seen: set[Path] = set()
    for path in paths:
        if not path.exists() or path.is_dir():
            continue
        resolved = path.resolve()
        if resolved in seen:
            continue
        seen.add(resolved)
        rel = relative(resolved)
        target = backup_dir / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(resolved, target)
        manifest["files"].append(
            {
                "path": rel,
                "backupPath": str(target.relative_to(ROOT)).replace("\\", "/"),
                "bytes": resolved.stat().st_size,
                "sha256": sha256_file(resolved),
                "modifiedAt": dt.datetime.fromtimestamp(resolved.stat().st_mtime).isoformat(timespec="seconds"),
            }
        )
    manifest_path = backup_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"backupId": backup_id, "backupPath": relative(backup_dir), "manifestPath": relative(manifest_path), "manifest": manifest}


def json_param(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False)


def upsert_raw_file(cursor, path: Path, file_hash: str, backup_lookup: dict[str, str]) -> None:
    payload: Any = None
    if path.suffix.lower() == ".json":
        raw = safe_json_load(path)
        if isinstance(raw, dict):
            payload = {
                "request": raw.get("request", {}),
                "summary": raw.get("summary", {}),
                "responseKeys": sorted(raw.get("response", {}).keys()) if isinstance(raw.get("response"), dict) else [],
            }
        else:
            payload = {}
    elif path.suffix.lower() == ".csv":
        with path.open("r", encoding="utf-8", newline="") as handle:
            reader = csv.reader(handle)
            headers = next(reader, [])
            row_count = sum(1 for _ in reader)
        payload = {"columns": headers, "rowCount": row_count}
    meta = metadata_from_name(path)
    cursor.execute(
        """
        INSERT INTO seo_raw_files (
            file_sha256, source, relative_path, file_name, extension, bytes,
            modified_at, backed_up_path, payload, uploaded_at
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, NOW())
        ON CONFLICT (file_sha256) DO UPDATE SET
            source = EXCLUDED.source,
            relative_path = EXCLUDED.relative_path,
            file_name = EXCLUDED.file_name,
            extension = EXCLUDED.extension,
            bytes = EXCLUDED.bytes,
            modified_at = EXCLUDED.modified_at,
            backed_up_path = EXCLUDED.backed_up_path,
            payload = EXCLUDED.payload,
            uploaded_at = NOW()
        """,
        (
            file_hash,
            meta.get("source", source_for_path(path)),
            relative(path),
            path.name,
            path.suffix.lower().lstrip("."),
            path.stat().st_size,
            dt.datetime.fromtimestamp(path.stat().st_mtime).isoformat(),
            backup_lookup.get(relative(path), ""),
            json_param(payload),
        ),
    )


def upload_gsc_csv(cursor, path: Path, file_hash: str) -> int:
    if path.suffix.lower() != ".csv" or not path.name.startswith("gsc_"):
        return 0
    meta = metadata_from_name(path)
    rows = read_csv(path)
    for index, row in enumerate(rows, start=1):
        cursor.execute(
            """
            INSERT INTO gsc_performance_rows (
                file_sha256, row_index, site_property, start_date, end_date, dimensions,
                date, query, page, clicks, impressions, ctr, position, raw_row, uploaded_at
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, NOW())
            ON CONFLICT (file_sha256, row_index) DO UPDATE SET
                site_property = EXCLUDED.site_property,
                start_date = EXCLUDED.start_date,
                end_date = EXCLUDED.end_date,
                dimensions = EXCLUDED.dimensions,
                date = EXCLUDED.date,
                query = EXCLUDED.query,
                page = EXCLUDED.page,
                clicks = EXCLUDED.clicks,
                impressions = EXCLUDED.impressions,
                ctr = EXCLUDED.ctr,
                position = EXCLUDED.position,
                raw_row = EXCLUDED.raw_row,
                uploaded_at = NOW()
            """,
            (
                file_hash,
                index,
                meta.get("site_property", ""),
                meta.get("start_date"),
                meta.get("end_date"),
                meta.get("dimensions", []),
                parse_date(row.get("date", "")),
                row.get("query", ""),
                row.get("page", ""),
                number(row.get("clicks")),
                number(row.get("impressions")),
                number(row.get("ctr")),
                number(row.get("position")),
                json_param(row),
            ),
        )
    return len(rows)


def upload_ga4_json(cursor, path: Path, file_hash: str) -> int:
    if path.suffix.lower() != ".json" or not path.name.startswith("ga4_"):
        return 0
    data = safe_json_load(path) or {}
    meta = metadata_from_name(path)
    response = data.get("response", {}) if isinstance(data, dict) else {}
    rows = response.get("rows", []) if isinstance(response, dict) else []
    dimensions = [item.get("name", "") for item in response.get("dimensionHeaders", [])]
    metrics = [item.get("name", "") for item in response.get("metricHeaders", [])]
    count = 0
    for index, row in enumerate(rows, start=1):
        item: dict[str, Any] = {}
        for idx, name in enumerate(dimensions):
            values = row.get("dimensionValues", [])
            item[name] = values[idx].get("value", "") if idx < len(values) else ""
        for idx, name in enumerate(metrics):
            values = row.get("metricValues", [])
            item[name] = number(values[idx].get("value", 0)) if idx < len(values) else 0
        cursor.execute(
            """
            INSERT INTO ga4_report_rows (
                file_sha256, row_index, property_id, start_date, end_date, date,
                session_default_channel_group, sessions, total_users, active_users,
                screen_page_views, engaged_sessions, raw_row, uploaded_at
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, NOW())
            ON CONFLICT (file_sha256, row_index) DO UPDATE SET
                property_id = EXCLUDED.property_id,
                start_date = EXCLUDED.start_date,
                end_date = EXCLUDED.end_date,
                date = EXCLUDED.date,
                session_default_channel_group = EXCLUDED.session_default_channel_group,
                sessions = EXCLUDED.sessions,
                total_users = EXCLUDED.total_users,
                active_users = EXCLUDED.active_users,
                screen_page_views = EXCLUDED.screen_page_views,
                engaged_sessions = EXCLUDED.engaged_sessions,
                raw_row = EXCLUDED.raw_row,
                uploaded_at = NOW()
            """,
            (
                file_hash,
                index,
                meta.get("property_id", ""),
                meta.get("start_date"),
                meta.get("end_date"),
                parse_date(str(item.get("date", ""))),
                str(item.get("sessionDefaultChannelGroup", "")),
                number(item.get("sessions")),
                number(item.get("totalUsers")),
                number(item.get("activeUsers")),
                number(item.get("screenPageViews")),
                number(item.get("engagedSessions")),
                json_param(item),
            ),
        )
        count += 1
    return count


def upload_pagespeed_json(cursor, path: Path, file_hash: str) -> int:
    if path.suffix.lower() != ".json" or not path.name.startswith("pagespeed_"):
        return 0
    data = safe_json_load(path) or {}
    meta = metadata_from_name(path)
    summary = data.get("summary", {}) if isinstance(data, dict) else {}
    scores = summary.get("scores", {}) if isinstance(summary.get("scores"), dict) else {}
    metrics = summary.get("coreMetrics", {}) if isinstance(summary.get("coreMetrics"), dict) else {}
    cursor.execute(
        """
        INSERT INTO pagespeed_report_runs (
            file_sha256, requested_url, final_url, strategy, fetched_at, performance,
            accessibility, best_practices, seo, lcp, tbt, cls, speed_index, summary, uploaded_at
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, NOW())
        ON CONFLICT (file_sha256) DO UPDATE SET
            requested_url = EXCLUDED.requested_url,
            final_url = EXCLUDED.final_url,
            strategy = EXCLUDED.strategy,
            fetched_at = EXCLUDED.fetched_at,
            performance = EXCLUDED.performance,
            accessibility = EXCLUDED.accessibility,
            best_practices = EXCLUDED.best_practices,
            seo = EXCLUDED.seo,
            lcp = EXCLUDED.lcp,
            tbt = EXCLUDED.tbt,
            cls = EXCLUDED.cls,
            speed_index = EXCLUDED.speed_index,
            summary = EXCLUDED.summary,
            uploaded_at = NOW()
        """,
        (
            file_hash,
            summary.get("requestedUrl", ""),
            summary.get("finalUrl", ""),
            meta.get("strategy", ""),
            parse_timestamp(str(summary.get("fetchTime", ""))),
            number(scores.get("performance")),
            number(scores.get("accessibility")),
            number(scores.get("best-practices")),
            number(scores.get("seo")),
            str(metrics.get("largest-contentful-paint", "")),
            str(metrics.get("total-blocking-time", "")),
            str(metrics.get("cumulative-layout-shift", "")),
            str(metrics.get("speed-index", "")),
            json_param(summary),
        ),
    )
    return 1


def upload_crux_json(cursor, path: Path, file_hash: str) -> int:
    if path.suffix.lower() != ".json" or not path.name.startswith("crux_"):
        return 0
    data = safe_json_load(path) or {}
    meta = metadata_from_name(path)
    summary = data.get("summary", {}) if isinstance(data, dict) else {}
    key = summary.get("key", {}) if isinstance(summary.get("key"), dict) else {}
    target = key.get("url") or key.get("origin") or ""
    cursor.execute(
        """
        INSERT INTO crux_report_runs (
            file_sha256, target_type, target, form_factor, collection_period, summary, uploaded_at
        )
        VALUES (%s, %s, %s, %s, %s::jsonb, %s::jsonb, NOW())
        ON CONFLICT (file_sha256) DO UPDATE SET
            target_type = EXCLUDED.target_type,
            target = EXCLUDED.target,
            form_factor = EXCLUDED.form_factor,
            collection_period = EXCLUDED.collection_period,
            summary = EXCLUDED.summary,
            uploaded_at = NOW()
        """,
        (
            file_hash,
            meta.get("target_type", ""),
            target,
            meta.get("form_factor", ""),
            json_param(summary.get("collectionPeriod", {})),
            json_param(summary),
        ),
    )
    return 1


def upload_sqlite_tables(cursor) -> int:
    if not LOCAL_SQLITE.exists():
        return 0
    count = 0
    conn = sqlite3.connect(LOCAL_SQLITE)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute("SELECT * FROM api_runs ORDER BY id").fetchall()
    except sqlite3.Error:
        rows = []
    for row in rows:
        item = dict(row)
        try:
            summary = json.loads(item.get("summary_json") or "{}")
        except json.JSONDecodeError:
            summary = {}
        cursor.execute(
            """
            INSERT INTO seo_api_runs (
                local_id, source, status, command, summary, raw_path, error, created_at, uploaded_at
            )
            VALUES (%s, %s, %s, %s, %s::jsonb, %s, %s, %s, NOW())
            ON CONFLICT (source, local_id) DO UPDATE SET
                status = EXCLUDED.status,
                command = EXCLUDED.command,
                summary = EXCLUDED.summary,
                raw_path = EXCLUDED.raw_path,
                error = EXCLUDED.error,
                created_at = EXCLUDED.created_at,
                uploaded_at = NOW()
            """,
            (
                item.get("id"),
                item.get("source", ""),
                item.get("status", ""),
                item.get("command", ""),
                json_param(summary),
                item.get("raw_path", ""),
                item.get("error", ""),
                item.get("created_at"),
            ),
        )
        count += 1
    conn.close()
    return count


def upload_backup_manifest(cursor, backup: dict[str, Any]) -> None:
    cursor.execute(
        """
        INSERT INTO local_backup_manifests (backup_id, label, backup_path, manifest, created_at)
        VALUES (%s, %s, %s, %s::jsonb, NOW())
        ON CONFLICT (backup_id) DO UPDATE SET
            label = EXCLUDED.label,
            backup_path = EXCLUDED.backup_path,
            manifest = EXCLUDED.manifest
        """,
        (
            backup["backupId"],
            backup["manifest"].get("label", ""),
            backup["backupPath"],
            json_param(backup["manifest"]),
        ),
    )


def upload_files(paths: list[Path], label: str = "manual_upload") -> dict[str, Any]:
    if not is_supabase_configured():
        return {"ok": False, "skipped": True, "reason": "Supabase is not configured."}
    selected = [path.resolve() for path in paths if path.exists() and path.is_file()]
    if LOCAL_SQLITE.exists():
        selected.append(LOCAL_SQLITE.resolve())
    backup = make_backup(selected, label)
    backup_lookup = {item["path"]: item["backupPath"] for item in backup["manifest"]["files"]}
    upload_paths = [path for path in selected if path != LOCAL_SQLITE.resolve()]
    result = {
        "ok": True,
        "backupId": backup["backupId"],
        "backupPath": backup["backupPath"],
        "files": 0,
        "gscRows": 0,
        "ga4Rows": 0,
        "pagespeedRuns": 0,
        "cruxRuns": 0,
        "apiRuns": 0,
    }
    conn = connect()
    try:
        init_schema(conn)
        cursor = conn.cursor()
        upload_backup_manifest(cursor, backup)
        conn.commit()
        for path in upload_paths:
            file_hash = sha256_file(path)
            upsert_raw_file(cursor, path, file_hash, backup_lookup)
            result["files"] += 1
            result["gscRows"] += upload_gsc_csv(cursor, path, file_hash)
            result["ga4Rows"] += upload_ga4_json(cursor, path, file_hash)
            result["pagespeedRuns"] += upload_pagespeed_json(cursor, path, file_hash)
            result["cruxRuns"] += upload_crux_json(cursor, path, file_hash)
            conn.commit()
        result["apiRuns"] = upload_sqlite_tables(cursor)
        conn.commit()
    except Exception:
        try:
            conn.rollback()
        except Exception:
            pass
        raise
    finally:
        try:
            conn.close()
        except Exception:
            pass
    return result


def auto_upload_files(paths: list[Path], label: str) -> dict[str, Any]:
    try:
        return upload_files(paths, label)
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "skipped": False, "error": str(exc)[:500]}


def all_data_files() -> list[Path]:
    files: list[Path] = []
    for directory in RAW_DIRS.values():
        if directory.exists():
            files.extend(path for path in directory.iterdir() if path.is_file() and path.suffix.lower() in {".csv", ".json"})
    return sorted(files, key=lambda item: str(item))


def upload_all() -> dict[str, Any]:
    return upload_files(all_data_files(), "manual_full_upload")


def health() -> dict[str, Any]:
    conn = connect()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT current_database(), current_user, version()")
        row = cursor.fetchone()
        return {"ok": True, "database": row[0], "user": row[1], "version": str(row[2]).split(" on ")[0]}
    finally:
        conn.close()


def latest_local_backup() -> dict[str, Any] | None:
    if not BACKUP_ROOT.exists():
        return None
    backups = [path for path in BACKUP_ROOT.iterdir() if path.is_dir()]
    if not backups:
        return None
    latest = max(backups, key=lambda item: item.stat().st_mtime)
    manifest_path = latest / "manifest.json"
    manifest = safe_json_load(manifest_path) if manifest_path.exists() else {}
    return {
        "backupId": latest.name,
        "backupPath": relative(latest),
        "manifestPath": relative(manifest_path) if manifest_path.exists() else "",
        "createdAt": manifest.get("createdAt", "") if isinstance(manifest, dict) else "",
        "label": manifest.get("label", "") if isinstance(manifest, dict) else "",
        "files": len(manifest.get("files", [])) if isinstance(manifest, dict) and isinstance(manifest.get("files"), list) else 0,
    }


def cloud_status() -> dict[str, Any]:
    configured = is_supabase_configured()
    status: dict[str, Any] = {
        "configured": configured,
        "ok": False,
        "health": {},
        "tableCounts": {},
        "latestBackup": latest_local_backup(),
    }
    if not configured:
        status["message"] = "Supabase is not configured."
        return status
    conn = None
    try:
        conn = connect(timeout=5)
        cursor = conn.cursor()
        cursor.execute("SELECT current_database(), current_user, version(), pg_database_size(current_database())")
        row = cursor.fetchone()
        status["health"] = {
            "database": row[0],
            "user": row[1],
            "version": str(row[2]).split(" on ")[0],
            "databaseBytes": int(row[3] or 0),
        }
        counts: dict[str, int] = {}
        for table in [
            "seo_raw_files",
            "gsc_performance_rows",
            "ga4_report_rows",
            "pagespeed_report_runs",
            "crux_report_runs",
            "seo_api_runs",
            "local_backup_manifests",
        ]:
            cursor.execute(f"SELECT COUNT(*) FROM {table}")
            counts[table] = int(cursor.fetchone()[0])
        status["tableCounts"] = counts
        status["ok"] = True
        status["message"] = "Supabase connection is healthy."
    except Exception as exc:  # noqa: BLE001
        if conn:
            try:
                conn.rollback()
            except Exception:
                pass
        status["message"] = "Supabase connection is unavailable or timed out. Local data remains available."
        status["errorType"] = type(exc).__name__
    finally:
        if conn:
            try:
                conn.close()
            except Exception:
                pass
    return status


def main() -> None:
    command = sys.argv[1] if len(sys.argv) > 1 else "health"
    if command == "health":
        print(json.dumps(health(), ensure_ascii=False, indent=2))
    elif command == "upload-all":
        print(json.dumps(upload_all(), ensure_ascii=False, indent=2))
    else:
        raise SystemExit("Usage: python -m apps.api.db.cloud_sync [health|upload-all]")


if __name__ == "__main__":
    main()
