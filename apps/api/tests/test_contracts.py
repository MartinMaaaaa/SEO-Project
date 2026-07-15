from __future__ import annotations

from fastapi.testclient import TestClient

from apps.api.main import app
import datetime as dt

from apps.api.services.analytics import _comparison_trend_table, _trend_period


client = TestClient(app)


def test_cached_endpoints_are_available() -> None:
    for path in ("/api/health", "/api/status", "/api/storage/overview", "/api/gsc/explorer", "/api/ga4/analytics", "/api/pagespeed/history", "/api/crux/summary", "/api/ai/tasks", "/api/saved-views", "/api/annotations"):
        assert client.get(path).status_code == 200


def test_gsc_metric_semantics_and_metadata() -> None:
    body = client.get("/api/gsc/explorer?preset=28&comparison=previous_period&grain=week").json()
    assert body["status"] in {"ok", "no_data"}
    if body["status"] == "ok":
        totals = body["totals"]
        assert totals["ctr"] == (round(totals["clicks"] / totals["impressions"], 6) if totals["impressions"] else 0)
        capabilities = body["metadata"]["dimensionCapabilities"]
        for dimension in ("country", "device", "searchAppearance"):
            assert body["metadata"]["availableDimensions"][dimension] is bool(capabilities[dimension]["enabled"])
            assert capabilities[dimension]["grain"]
            assert capabilities[dimension]["scope"] == "property"
        assert body["comparison"]["status"] in {"complete", "partial", "unavailable", "none"}
        assert body["comparison"]["alignment"] == "backend_offset_key"
        assert all(row["alignmentKey"].startswith(f'{body["scope"]["grain"]}:') for row in body["trend"])
        assert body["metadata"]["grain"] == body["scope"]["grain"]
        assert body["metadata"]["latestCompleteDate"] == body["metadata"]["cacheCoverage"]["end"]
        assert body["metadata"]["dataQuality"]["coverageStatus"] in {"complete", "partial"}
        if body["comparison"]["status"] != "complete":
            assert body["previousTotals"] is None
            assert body["deltas"] is None
            assert body["comparisonTrend"] == []
            assert body["comparison"]["reasonCode"]
        else:
            assert all(row["alignmentKey"].startswith(f'{body["scope"]["grain"]}:') for row in body["comparisonTrend"])


def test_aligned_trend_contract_preserves_aggregated_formulas_and_missing_buckets() -> None:
    rows = [
        {"date": "2026-01-01", "clicks": "1", "impressions": "10", "position": "2"},
        {"date": "2026-01-01", "clicks": "2", "impressions": "30", "position": "4"},
        {"date": "2026-01-03", "clicks": "0", "impressions": "5", "position": "8"},
    ]
    trend = _trend_period(rows, "day", dt.date(2026, 1, 1))
    assert [row["alignmentKey"] for row in trend] == ["day:0", "day:2"]
    assert [row["label"] for row in trend] == ["2026-01-01", "2026-01-03"]
    assert trend[0]["clicks"] == 3
    assert trend[0]["ctr"] == 0.075
    assert trend[0]["position"] == 3.5
    assert trend[1]["clicks"] == 0


def test_alignment_offsets_are_stable_across_current_and_comparison_missing_buckets() -> None:
    current = [
        {"date": "2026-02-01", "clicks": "2", "impressions": "20", "position": "3"},
        {"date": "2026-02-03", "clicks": "4", "impressions": "40", "position": "5"},
    ]
    previous = [
        {"date": "2026-01-29", "clicks": "1", "impressions": "10", "position": "4"},
        {"date": "2026-01-30", "clicks": "3", "impressions": "30", "position": "6"},
    ]
    current_trend = _trend_period(current, "day", dt.date(2026, 2, 1))
    previous_trend = _trend_period(previous, "day", dt.date(2026, 1, 29))
    assert [row["alignmentKey"] for row in current_trend] == ["day:0", "day:2"]
    assert [row["alignmentKey"] for row in previous_trend] == ["day:0", "day:1"]
    assert not any(row["alignmentKey"] == "day:1" for row in current_trend)

    table = _comparison_trend_table(current_trend, previous_trend, 2, True)
    assert table[0]["comparisonLabel"] == "2026-01-29"
    assert table[0]["previous_clicks"] == 1
    assert table[1]["comparisonLabel"] is None
    assert table[1]["previous_clicks"] is None
    assert table[1]["delta_clicks"] is None


def test_cached_complete_comparison_uses_same_trend_rows_for_date_table() -> None:
    body = client.get("/api/gsc/explorer?preset=7&comparison=previous_period&grain=day").json()
    if body["status"] == "ok" and body["comparison"]["status"] == "complete":
        assert body["tables"]["date"] == body["tables"]["date"][: body["scope"]["rowLimit"]]
        assert [row["alignmentKey"] for row in body["tables"]["date"]] == [row["alignmentKey"] for row in body["trend"]]
        comparison = {row["alignmentKey"]: row for row in body["comparisonTrend"]}
        for row in body["tables"]["date"]:
            previous = comparison.get(row["alignmentKey"])
            assert row["comparisonLabel"] == (previous["label"] if previous else None)
            assert row["previous_clicks"] == (previous["clicks"] if previous else None)


def test_pagespeed_failures_have_no_score() -> None:
    body = client.get("/api/pagespeed/history").json()
    for run in body["runs"]:
        if run["status"] == "failed":
            assert run["displayStatus"] == "Run failed"
            assert run["scores"] is None


def test_crux_missing_coverage_is_not_a_failure_score() -> None:
    body = client.get("/api/crux/summary").json()
    if body["status"] == "no_data":
        assert body["displayStatus"] == "No dataset"
        assert body["summary"] == {}


def test_scoped_ai_task_can_be_created_and_listed() -> None:
    response = client.post("/api/ai/tasks", json={"taskType": "contract_test", "title": "Contract test task", "scope": {"source": "cached"}, "evidence": {"clicks": 1}})
    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    from apps.api.core.config import ROOT
    path = ROOT / body["path"]
    assert path.exists()
    assert any(item["path"] == body["path"] for item in client.get("/api/ai/tasks").json())
    path.unlink()
