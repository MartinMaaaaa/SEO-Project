"""Persistent saved analysis views and annotations for the active dashboard."""

from __future__ import annotations

import datetime as dt
import json
from pathlib import Path
import sqlite3
from typing import Any

from apps.api.db.local_store import DB_PATH


FORBIDDEN_CONFIG_TOKENS = ("secret", "token", "password", "credential", "authorization", "rawrows", "raw_rows")


def connect(db_path: Path = DB_PATH) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    init_db(conn)
    return conn


def init_db(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS saved_analysis_views (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            description TEXT NOT NULL DEFAULT '',
            source TEXT NOT NULL,
            is_favorite INTEGER NOT NULL DEFAULT 0,
            config_json TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_saved_analysis_views_source_updated
            ON saved_analysis_views(source, updated_at DESC, id DESC);

        CREATE TABLE IF NOT EXISTS analysis_annotations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            annotation_date TEXT NOT NULL,
            annotation_time TEXT NOT NULL DEFAULT '',
            title TEXT NOT NULL,
            annotation_type TEXT NOT NULL,
            affected_url TEXT NOT NULL DEFAULT '',
            affected_query TEXT NOT NULL DEFAULT '',
            affected_page_group TEXT NOT NULL DEFAULT '',
            notes TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_analysis_annotations_date
            ON analysis_annotations(annotation_date DESC, id DESC);
        CREATE INDEX IF NOT EXISTS idx_analysis_annotations_url
            ON analysis_annotations(affected_url);
        CREATE INDEX IF NOT EXISTS idx_analysis_annotations_query
            ON analysis_annotations(affected_query);
        """
    )
    conn.commit()


def _now() -> str:
    return dt.datetime.now().isoformat(timespec="seconds")


def validate_config(config: dict[str, Any]) -> None:
    encoded = json.dumps(config, ensure_ascii=False)
    if len(encoded.encode("utf-8")) > 100_000:
        raise ValueError("Saved view configuration exceeds 100 KB")

    def visit(value: Any, path: str = "config") -> None:
        if isinstance(value, dict):
            for key, child in value.items():
                normalized = str(key).casefold().replace("-", "_")
                if any(token in normalized for token in FORBIDDEN_CONFIG_TOKENS):
                    raise ValueError(f"Saved view cannot contain sensitive field: {path}.{key}")
                visit(child, f"{path}.{key}")
        elif isinstance(value, list):
            for index, child in enumerate(value):
                visit(child, f"{path}[{index}]")
    visit(config)


def _saved_view(row: sqlite3.Row) -> dict[str, Any]:
    item = dict(row)
    item["isFavorite"] = bool(item.pop("is_favorite"))
    item["createdAt"] = item.pop("created_at")
    item["updatedAt"] = item.pop("updated_at")
    item["config"] = json.loads(item.pop("config_json"))
    return item


def list_saved_views(source: str = "") -> list[dict[str, Any]]:
    with connect() as conn:
        if source:
            rows = conn.execute("SELECT * FROM saved_analysis_views WHERE source = ? ORDER BY is_favorite DESC, updated_at DESC, id DESC", (source,)).fetchall()
        else:
            rows = conn.execute("SELECT * FROM saved_analysis_views ORDER BY is_favorite DESC, updated_at DESC, id DESC").fetchall()
    return [_saved_view(row) for row in rows]


def get_saved_view(view_id: int) -> dict[str, Any] | None:
    with connect() as conn:
        row = conn.execute("SELECT * FROM saved_analysis_views WHERE id = ?", (view_id,)).fetchone()
    return _saved_view(row) if row else None


def create_saved_view(payload: dict[str, Any]) -> dict[str, Any]:
    config = payload.get("config") if isinstance(payload.get("config"), dict) else {}
    validate_config(config)
    stamp = _now()
    with connect() as conn:
        cursor = conn.execute(
            "INSERT INTO saved_analysis_views (name, description, source, is_favorite, config_json, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (str(payload.get("name") or "Untitled view").strip(), str(payload.get("description") or "").strip(), str(payload.get("source") or "gsc").strip(), int(bool(payload.get("isFavorite"))), json.dumps(config, ensure_ascii=False), stamp, stamp),
        )
        conn.commit()
        view_id = int(cursor.lastrowid)
    return get_saved_view(view_id) or {}


def update_saved_view(view_id: int, payload: dict[str, Any]) -> dict[str, Any] | None:
    current = get_saved_view(view_id)
    if not current:
        return None
    config = payload.get("config", current["config"])
    if not isinstance(config, dict):
        raise ValueError("Saved view config must be an object")
    validate_config(config)
    with connect() as conn:
        conn.execute(
            "UPDATE saved_analysis_views SET name = ?, description = ?, source = ?, is_favorite = ?, config_json = ?, updated_at = ? WHERE id = ?",
            (str(payload.get("name", current["name"])).strip(), str(payload.get("description", current["description"])).strip(), str(payload.get("source", current["source"])).strip(), int(bool(payload.get("isFavorite", current["isFavorite"]))), json.dumps(config, ensure_ascii=False), _now(), view_id),
        )
        conn.commit()
    return get_saved_view(view_id)


def delete_saved_view(view_id: int) -> bool:
    with connect() as conn:
        cursor = conn.execute("DELETE FROM saved_analysis_views WHERE id = ?", (view_id,))
        conn.commit()
    return cursor.rowcount > 0


def _annotation(row: sqlite3.Row) -> dict[str, Any]:
    item = dict(row)
    return {
        "id": item["id"], "date": item["annotation_date"], "time": item["annotation_time"],
        "title": item["title"], "type": item["annotation_type"], "affectedUrl": item["affected_url"],
        "affectedQuery": item["affected_query"], "affectedPageGroup": item["affected_page_group"],
        "notes": item["notes"], "createdAt": item["created_at"], "updatedAt": item["updated_at"],
    }


def list_annotations(start: str = "", end: str = "", query: str = "", url: str = "") -> list[dict[str, Any]]:
    clauses, values = [], []
    if start: clauses.append("annotation_date >= ?"); values.append(start)
    if end: clauses.append("annotation_date <= ?"); values.append(end)
    if query: clauses.append("(affected_query = '' OR lower(affected_query) = lower(?))"); values.append(query)
    if url: clauses.append("(affected_url = '' OR affected_url = ?)"); values.append(url)
    where = f" WHERE {' AND '.join(clauses)}" if clauses else ""
    with connect() as conn:
        rows = conn.execute(f"SELECT * FROM analysis_annotations{where} ORDER BY annotation_date DESC, annotation_time DESC, id DESC", values).fetchall()
    return [_annotation(row) for row in rows]


def get_annotation(annotation_id: int) -> dict[str, Any] | None:
    with connect() as conn:
        row = conn.execute("SELECT * FROM analysis_annotations WHERE id = ?", (annotation_id,)).fetchone()
    return _annotation(row) if row else None


def create_annotation(payload: dict[str, Any]) -> dict[str, Any]:
    stamp = _now()
    with connect() as conn:
        cursor = conn.execute(
            """INSERT INTO analysis_annotations (
                annotation_date, annotation_time, title, annotation_type, affected_url,
                affected_query, affected_page_group, notes, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (str(payload.get("date") or dt.date.today().isoformat()), str(payload.get("time") or ""), str(payload.get("title") or "Untitled annotation").strip(), str(payload.get("type") or "note").strip(), str(payload.get("affectedUrl") or "").strip(), str(payload.get("affectedQuery") or "").strip(), str(payload.get("affectedPageGroup") or "").strip(), str(payload.get("notes") or "").strip(), stamp, stamp),
        )
        conn.commit()
        annotation_id = int(cursor.lastrowid)
    return get_annotation(annotation_id) or {}


def update_annotation(annotation_id: int, payload: dict[str, Any]) -> dict[str, Any] | None:
    current = get_annotation(annotation_id)
    if not current: return None
    with connect() as conn:
        conn.execute(
            """UPDATE analysis_annotations SET annotation_date = ?, annotation_time = ?, title = ?, annotation_type = ?,
                affected_url = ?, affected_query = ?, affected_page_group = ?, notes = ?, updated_at = ? WHERE id = ?""",
            (str(payload.get("date", current["date"])), str(payload.get("time", current["time"])), str(payload.get("title", current["title"])).strip(), str(payload.get("type", current["type"])).strip(), str(payload.get("affectedUrl", current["affectedUrl"])).strip(), str(payload.get("affectedQuery", current["affectedQuery"])).strip(), str(payload.get("affectedPageGroup", current["affectedPageGroup"])).strip(), str(payload.get("notes", current["notes"])).strip(), _now(), annotation_id),
        )
        conn.commit()
    return get_annotation(annotation_id)


def delete_annotation(annotation_id: int) -> bool:
    with connect() as conn:
        cursor = conn.execute("DELETE FROM analysis_annotations WHERE id = ?", (annotation_id,))
        conn.commit()
    return cursor.rowcount > 0


def storage_counts(db_path: Path = DB_PATH) -> dict[str, int]:
    with connect(db_path) as conn:
        views = int(conn.execute("SELECT COUNT(*) FROM saved_analysis_views").fetchone()[0])
        annotations = int(conn.execute("SELECT COUNT(*) FROM analysis_annotations").fetchone()[0])
    return {"savedViews": views, "annotations": annotations}
