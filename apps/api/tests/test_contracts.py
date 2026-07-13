from __future__ import annotations

from fastapi.testclient import TestClient

from apps.api.main import app


client = TestClient(app)


def test_cached_endpoints_are_available() -> None:
    for path in ("/api/health", "/api/status", "/api/storage/overview", "/api/gsc/explorer", "/api/ga4/analytics", "/api/pagespeed/history", "/api/crux/summary", "/api/ai/tasks"):
        assert client.get(path).status_code == 200


def test_gsc_metric_semantics_and_metadata() -> None:
    body = client.get("/api/gsc/explorer?preset=28&comparison=previous_period&grain=week").json()
    assert body["status"] in {"ok", "no_data"}
    if body["status"] == "ok":
        totals = body["totals"]
        assert totals["ctr"] == (round(totals["clicks"] / totals["impressions"], 6) if totals["impressions"] else 0)
        assert body["metadata"]["availableDimensions"]["country"] is False
        assert body["comparison"]["status"] in {"complete", "partial", "unavailable", "none"}
        if body["comparison"]["status"] != "complete":
            assert body["previousTotals"] is None
            assert body["deltas"] is None


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
