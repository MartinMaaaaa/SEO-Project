from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

from apps.api.db import gsc_store
from apps.api.services import analytics


def write_export(
    path: Path,
    dimensions: list[str],
    rows: list[dict[str, object]],
    *,
    filters: list[dict[str, object]] | None = None,
    row_limit: int = 25000,
) -> None:
    request: dict[str, object] = {
        "startDate": "2026-07-01",
        "endDate": "2026-07-04",
        "dimensions": dimensions,
        "type": "web",
        "dataState": "final",
        "rowLimit": row_limit,
        "startRow": 0,
    }
    if filters:
        request["dimensionFilterGroups"] = [{"groupType": "and", "filters": filters}]
    payload = {
        "request": request,
        "siteUrl": "sc-domain:example.test",
        "response": {"responseAggregationType": "byProperty", "rows": rows},
    }
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_duplicate_import_replaces_the_same_scope(tmp_path: Path) -> None:
    db_path = tmp_path / "gsc.sqlite"
    export = tmp_path / "country.json"
    write_export(
        export,
        ["date", "country"],
        [
            {"keys": ["2026-07-01", "usa"], "clicks": 2, "impressions": 10, "ctr": 0.2, "position": 3},
            {"keys": ["2026-07-02", "usa"], "clicks": 1, "impressions": 30, "ctr": 0.0333, "position": 5},
        ],
    )
    gsc_store.import_export(export, db_path)
    gsc_store.import_export(export, db_path)
    assert gsc_store.storage_counts(db_path) == {"exports": 1, "rows": 2}


def test_dimension_aggregation_recomputes_ctr_and_weights_position(tmp_path: Path) -> None:
    db_path = tmp_path / "gsc.sqlite"
    export = tmp_path / "country.json"
    write_export(
        export,
        ["date", "country"],
        [
            {"keys": ["2026-07-01", "usa"], "clicks": 2, "impressions": 10, "ctr": 0.2, "position": 3},
            {"keys": ["2026-07-02", "usa"], "clicks": 1, "impressions": 30, "ctr": 0.0333, "position": 5},
            {"keys": ["2026-07-03", "gbr"], "clicks": 4, "impressions": 20, "ctr": 0.2, "position": 2},
        ],
        row_limit=3,
    )
    gsc_store.import_export(export, db_path)
    result = gsc_store.dimension_breakdowns(
        dt.date(2026, 7, 1), dt.date(2026, 7, 4), None, "none", [], db_path
    )
    usa = next(item for item in result["tables"]["country"] if item["label"] == "usa")
    assert usa["clicks"] == 3
    assert usa["impressions"] == 40
    assert usa["ctr"] == 0.075
    assert usa["position"] == 4.5
    assert result["capabilities"]["country"]["rowLimitReached"] is True
    assert any("row limit" in notice for notice in result["notices"])


def test_missing_or_incompatible_dimensions_stay_disabled(tmp_path: Path) -> None:
    db_path = tmp_path / "gsc.sqlite"
    export = tmp_path / "device.json"
    write_export(export, ["date", "device"], [{"keys": ["2026-07-01", "MOBILE"], "clicks": 1, "impressions": 5, "ctr": 0.2, "position": 2}])
    gsc_store.import_export(export, db_path)
    result = gsc_store.dimension_breakdowns(
        dt.date(2026, 7, 1), dt.date(2026, 7, 4), None, "none",
        [{"field": "query", "operator": "contains", "value": "solar"}], db_path,
    )
    assert result["capabilities"]["device"]["available"] is True
    assert result["capabilities"]["device"]["enabled"] is False
    assert "cannot be combined" in result["capabilities"]["device"]["reason"]
    assert result["capabilities"]["country"]["available"] is False
    assert result["tables"]["device"] == []


def test_two_step_search_appearance_exports_are_combined_without_inference(tmp_path: Path) -> None:
    db_path = tmp_path / "gsc.sqlite"
    for appearance, clicks in (("WEB_RESULT", 3), ("VIDEO", 2)):
        export = tmp_path / f"{appearance}.json"
        write_export(
            export,
            ["date"],
            [{"keys": ["2026-07-03"], "clicks": clicks, "impressions": 10, "ctr": clicks / 10, "position": 2}],
            filters=[{"dimension": "searchAppearance", "operator": "equals", "expression": appearance}],
        )
        gsc_store.import_export(export, db_path)
    result = gsc_store.dimension_breakdowns(
        dt.date(2026, 7, 1), dt.date(2026, 7, 4), None, "none", [], db_path
    )
    assert {item["label"] for item in result["tables"]["searchAppearance"]} == {"WEB_RESULT", "VIDEO"}
    assert result["capabilities"]["searchAppearance"]["grain"] == ["date", "searchAppearance"]
    assert result["capabilities"]["searchAppearance"]["scope"] == "property"


def test_dimension_comparison_uses_only_covered_rows(tmp_path: Path) -> None:
    db_path = tmp_path / "gsc.sqlite"
    export = tmp_path / "country.json"
    write_export(
        export,
        ["date", "country"],
        [
            {"keys": ["2026-07-01", "usa"], "clicks": 1, "impressions": 10, "ctr": 0.1, "position": 3},
            {"keys": ["2026-07-02", "usa"], "clicks": 1, "impressions": 10, "ctr": 0.1, "position": 3},
            {"keys": ["2026-07-03", "usa"], "clicks": 3, "impressions": 10, "ctr": 0.3, "position": 2},
            {"keys": ["2026-07-04", "usa"], "clicks": 3, "impressions": 10, "ctr": 0.3, "position": 2},
        ],
    )
    gsc_store.import_export(export, db_path)
    result = gsc_store.dimension_breakdowns(
        dt.date(2026, 7, 3), dt.date(2026, 7, 4),
        {"start": "2026-07-01", "end": "2026-07-02"}, "complete", [], db_path,
    )
    row = result["tables"]["country"][0]
    assert row["clicks"] == 6
    assert row["previous_clicks"] == 2
    assert row["delta_clicks"] == 4


def test_sync_orchestration_uses_separate_grains_and_two_step_appearance(monkeypatch) -> None:
    calls: list[tuple[tuple[str, ...], tuple[str, ...]]] = []

    def fake_query(dimensions: tuple[str, ...], filters: tuple[str, ...] = ()) -> dict[str, object]:
        calls.append((dimensions, filters))
        return {"ok": True, "newFiles": []}

    monkeypatch.setattr(analytics, "_run_gsc_query", fake_query)
    monkeypatch.setattr(analytics, "_appearance_values", lambda result: ["VIDEO", "WEB_RESULT"])
    result = analytics.run_gsc_sync(force=True)
    assert result["ok"] is True
    assert (("date", "country"), ()) in calls
    assert (("date", "device"), ()) in calls
    assert (("searchAppearance",), ()) in calls
    assert (("date",), ("searchAppearance:equals:VIDEO",)) in calls
    assert not any(set(dimensions) >= {"country", "device"} for dimensions, _ in calls)
    assert result["collectionContract"]["combinedGrainInferred"] is False
