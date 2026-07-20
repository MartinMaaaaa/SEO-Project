from __future__ import annotations

import json
from pathlib import Path

from apps.api.db import ga4_store
from apps.api.db.cloud_sync import metadata_from_name
from apps.api.services import analytics


METRICS = ["sessions", "totalUsers", "newUsers", "engagedSessions", "engagementRate", "screenPageViews"]


def write_report(
    path: Path,
    label: str,
    dimension: str | list[str],
    rows: list[tuple[list[str], list[float]]],
    metrics: list[str] | None = None,
    current_range: tuple[str, str] = ("2026-07-01", "2026-07-28"),
    comparison_range: tuple[str, str] = ("2026-06-03", "2026-06-30"),
) -> None:
    dimensions = [dimension] if isinstance(dimension, str) else dimension
    metric_names = metrics or METRICS
    payload = {
        "propertyId": "123456",
        "reportLabel": label,
        "request": {
            "dateRanges": [
                {"startDate": comparison_range[0], "endDate": comparison_range[1], "name": "comparison"},
                {"startDate": current_range[0], "endDate": current_range[1], "name": "current"},
            ],
            "dimensions": [{"name": item} for item in dimensions],
            "metrics": [{"name": item} for item in metric_names],
            "limit": "10000",
        },
        "response": {
            "dimensionHeaders": [{"name": item} for item in dimensions],
            "metricHeaders": [{"name": item, "type": "TYPE_FLOAT"} for item in metric_names],
            "rows": [
                {
                    "dimensionValues": [{"value": value} for value in dimension_values],
                    "metricValues": [{"value": str(value)} for value in metric_values],
                }
                for dimension_values, metric_values in rows
            ],
        },
    }
    path.write_text(json.dumps(payload), encoding="utf-8")


def base_reports(directory: Path) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    write_report(
        directory / "ga4_totals.json", "totals", ["dateRange", "sessionDefaultChannelGroup"],
        [(["current", "Organic Search"], [8, 10, 4, 6, 0.75, 20]), (["comparison", "Organic Search"], [4, 7, 2, 2, 0.5, 11])],
    )
    write_report(
        directory / "ga4_trend.json", "trend", ["dateRange", "date"],
        [
            (["current", "20260701"], [3, 7, 2, 2, 0.66, 8]),
            (["current", "20260702"], [5, 8, 2, 4, 0.8, 12]),
            (["comparison", "20260603"], [1, 3, 1, 1, 1, 4]),
            (["comparison", "20260604"], [3, 5, 1, 1, 0.33, 7]),
        ],
    )
    for label, dimension, current_label, previous_label in (
        ("source-medium", "sessionSourceMedium", "google / organic", "google / organic"),
        ("landing-page", "landingPagePlusQueryString", "/", "/"),
        ("device", "deviceCategory", "desktop", "desktop"),
        ("country", "country", "Netherlands", "Netherlands"),
    ):
        write_report(
            directory / f"ga4_{label}.json", label, ["dateRange", dimension],
            [(["current", current_label], [8, 10, 4, 6, 0.75, 20]), (["comparison", previous_label], [4, 7, 2, 2, 0.5, 11])],
        )


def test_ga4_contract_uses_period_reports_and_recomputes_rate(tmp_path: Path, monkeypatch) -> None:
    base_reports(tmp_path)
    monkeypatch.setitem(analytics.RAW, "ga4", tmp_path)
    monkeypatch.setattr(analytics, "_configured_events", lambda: [])
    body = analytics.ga4_analytics({})
    assert body["status"] == "ok"
    assert body["totals"]["totalUsers"] == 10
    assert body["totals"]["engagementRate"] == 0.75
    assert body["previousTotals"]["totalUsers"] == 7
    assert [row["alignmentKey"] for row in body["trend"]] == ["day:0", "day:1"]
    landing = body["tables"]["landingPage"][0]
    assert landing["sessions"] == 8
    assert landing["previous_sessions"] == 4
    assert landing["delta_sessions"] == 4
    assert landing["change_sessions"] == 1
    assert body["metadata"]["conversionState"] == "not_configured"
    assert "keyEvents" not in body["metadata"]["metrics"]


def test_ga4_configured_key_events_are_exposed_only_when_collected(tmp_path: Path, monkeypatch) -> None:
    base_reports(tmp_path)
    monkeypatch.setitem(analytics.RAW, "ga4", tmp_path)
    monkeypatch.setattr(analytics, "_configured_events", lambda: ["quote_request"])
    missing = analytics.ga4_analytics({})
    assert missing["metadata"]["conversionState"] == "not_collected"
    assert "keyEvents" not in missing["metadata"]["metrics"]

    write_report(
        tmp_path / "ga4_events.json", "configured-key-events", ["dateRange", "date", "landingPagePlusQueryString", "eventName"],
        [], metrics=["keyEvents"],
    )
    empty = analytics.ga4_analytics({})
    assert empty["metadata"]["conversionState"] == "not_collected"
    assert empty["metadata"]["dimensionCapabilities"]["event"]["available"] is False

    write_report(
        tmp_path / "ga4_events.json", "configured-key-events", ["dateRange", "date", "landingPagePlusQueryString", "eventName"],
        [
            (["current", "20260701", "/", "quote_request"], [2]),
            (["comparison", "20260603", "/", "quote_request"], [1]),
        ], metrics=["keyEvents"],
    )
    available = analytics.ga4_analytics({})
    assert available["metadata"]["conversionState"] == "available"
    assert available["totals"]["keyEvents"] == 2
    assert available["tables"]["landingPage"][0]["previous_keyEvents"] == 1
    assert available["tables"]["event"][0]["label"] == "quote_request"
    assert available["tables"]["event"][0]["delta_keyEvents"] == 1
    assert "keyEvents" in available["metadata"]["metrics"]


def test_ga4_selected_snapshot_never_borrows_an_incompatible_dimension_range(tmp_path: Path, monkeypatch) -> None:
    base_reports(tmp_path)
    write_report(
        tmp_path / "ga4_totals_new.json", "totals", ["dateRange", "sessionDefaultChannelGroup"],
        [(["current", "Organic Search"], [12, 13, 5, 8, 0.61, 24])],
        current_range=("2026-07-02", "2026-07-29"), comparison_range=("2026-06-04", "2026-07-01"),
    )
    monkeypatch.setitem(analytics.RAW, "ga4", tmp_path)
    monkeypatch.setattr(analytics, "_configured_events", lambda: [])

    latest = analytics.ga4_analytics({})
    assert latest["scope"]["range"] == {"start": "2026-07-02", "end": "2026-07-29"}
    assert latest["status"] == "partial"
    assert latest["tables"]["country"] == []
    assert latest["metadata"]["dimensionCapabilities"]["country"]["available"] is False

    prior = analytics.ga4_analytics({"start": ["2026-07-01"], "end": ["2026-07-28"]})
    assert prior["status"] == "ok"
    assert prior["tables"]["country"][0]["label"] == "Netherlands"
    assert len(prior["metadata"]["availableScopes"]) == 2


def test_ga4_custom_sync_range_uses_equal_previous_period_and_skips_exact_cache(tmp_path: Path, monkeypatch) -> None:
    base_reports(tmp_path)
    monkeypatch.setitem(analytics.RAW, "ga4", tmp_path)
    monkeypatch.setattr(analytics, "_configured_events", lambda: [])

    cached = analytics.run_ga4_sync(False, "2026-07-01", "2026-07-28")
    assert cached["status"] == "skipped_cached_scope"
    assert cached["apiCalls"] == 0

    calls: list[tuple[dict[str, str], dict[str, str]]] = []
    monkeypatch.setattr(analytics, "_run_ga4_query", lambda label, dimensions, metrics, current_range, comparison_range, **kwargs: calls.append((current_range, comparison_range)) or {"ok": False})
    result = analytics.run_ga4_sync(False, "2026-07-02", "2026-07-08")
    assert result["status"] == "error"
    assert calls[0] == (
        {"start": "2026-07-02", "end": "2026-07-08"},
        {"start": "2026-06-25", "end": "2026-07-01"},
    )


def test_ga4_store_replaces_identical_scope(tmp_path: Path) -> None:
    export = tmp_path / "report.json"
    write_report(export, "device", ["dateRange", "deviceCategory"], [(["current", "desktop"], [2, 2, 1, 1, 0.5, 4])])
    db_path = tmp_path / "ga4.sqlite"
    ga4_store.import_export(export, db_path)
    ga4_store.import_export(export, db_path)
    assert ga4_store.storage_counts(db_path) == {"exports": 1, "rows": 1}


def test_ga4_sync_uses_independent_validated_grains(monkeypatch) -> None:
    calls: list[tuple[str, tuple[str, ...], tuple[str, ...]]] = []
    monkeypatch.setattr(analytics, "_fresh_sync_skip", lambda *args, **kwargs: None)
    monkeypatch.setattr(analytics, "_configured_events", lambda: ["quote_request"])
    monkeypatch.setattr(analytics, "ga4_analytics", lambda params: {"metadata": {"latestCompleteDate": "2026-07-13"}})

    def fake_query(label, dimensions, metrics, current_range, comparison_range, **kwargs):
        calls.append((label, dimensions, metrics))
        return {"ok": True, "runId": len(calls), "newFiles": [f"{label}.json"], "normalizedImports": [{}], "cloudSync": {"skipped": True}}

    monkeypatch.setattr(analytics, "_run_ga4_query", fake_query)
    result = analytics.run_ga4_sync(force=True)
    assert result["status"] == "success"
    assert {label for label, _, _ in calls} == {"totals", "trend", "source-medium", "landing-page", "device", "country", "configured-key-events"}
    assert ("landing-page", ("landingPagePlusQueryString",), tuple(METRICS)) in calls
    assert result["collectionContract"]["combinedGrainInferred"] is False


def test_ga4_cloud_metadata_accepts_labeled_export_names() -> None:
    metadata = metadata_from_name(
        Path(
            "ga4_123456_landing-page_2026-06-16_2026-07-13_"
            "landingPagePlusQueryString_20260715_100912.json"
        )
    )
    assert metadata == {
        "source": "ga4",
        "property_id": "123456",
        "report_label": "landing-page",
        "start_date": "2026-06-16",
        "end_date": "2026-07-13",
        "dimensions": ["landingPagePlusQueryString"],
    }
