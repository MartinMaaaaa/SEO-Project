from __future__ import annotations

from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[3]
from apps.api.db import cloud_sync, local_store


def status() -> dict[str, Any]:
    sqlite_path = local_store.DB_PATH
    latest_backup = cloud_sync.latest_local_backup()
    return {
        "role": "local_backup",
        "sqlite": {
            "path": str(sqlite_path.relative_to(ROOT)).replace("\\", "/"),
            "exists": sqlite_path.exists(),
            "bytes": sqlite_path.stat().st_size if sqlite_path.exists() else 0,
        },
        "latestBackup": latest_backup,
        "rawDirectories": {
            source: directory_summary(path)
            for source, path in cloud_sync.RAW_DIRS.items()
        },
    }


def recent_runs(limit: int = 30) -> list[dict[str, Any]]:
    return local_store.recent_api_runs(limit)


def quota_sources(days: int = 30) -> list[dict[str, Any]]:
    return local_store.api_source_status(days)


def directory_summary(path: Path) -> dict[str, Any]:
    files = [item for item in path.iterdir() if item.is_file() and item.suffix.lower() in {".csv", ".json"}] if path.exists() else []
    latest = max(files, key=lambda item: item.stat().st_mtime) if files else None
    return {
        "path": str(path.relative_to(ROOT)).replace("\\", "/"),
        "exists": path.exists(),
        "files": len(files),
        "bytes": sum(item.stat().st_size for item in files),
        "latestFile": latest.name if latest else "",
    }
