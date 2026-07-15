from __future__ import annotations

from fastapi.testclient import TestClient

from apps.api.main import app


client = TestClient(app)


def complete_view_config() -> dict[str, object]:
    return {
        "version": 1,
        "date": {"mode": "relative", "preset": "28", "start": "", "end": ""},
        "comparison": {"mode": "previous_period"},
        "grain": "week",
        "filters": [
            {"field": "query", "operator": "contains", "value": "elecrest"},
            {"field": "page", "operator": "contains", "value": "/products/"},
        ],
        "chart": {"type": "time_series", "metric": "clicks", "visibleSeries": ["clicks", "impressions", "ctr", "position"], "displayMode": "unit_lanes"},
        "table": {"dimension": "page", "search": "battery", "sort": {"field": "clicks", "direction": "desc"}, "rowLimit": 100},
        "drilldown": {"dimension": "page", "value": "https://example.test/products/"},
    }


def test_saved_view_crud_preserves_complete_analysis_state() -> None:
    config = complete_view_config()
    created = client.post("/api/saved-views", json={"name": "GSC product view", "description": "Contract test", "source": "gsc", "isFavorite": True, "config": config})
    assert created.status_code == 200
    view = created.json()
    view_id = view["id"]
    try:
        assert view["config"] == config
        assert view["isFavorite"] is True
        assert client.get(f"/api/saved-views/{view_id}").json()["config"] == config
        assert any(item["id"] == view_id for item in client.get("/api/saved-views?source=gsc").json())
        updated_config = {**config, "grain": "month", "table": {**config["table"], "dimension": "query"}}
        updated = client.put(f"/api/saved-views/{view_id}", json={"name": "Updated view", "source": "gsc", "isFavorite": False, "config": updated_config})
        assert updated.status_code == 200
        assert updated.json()["config"]["grain"] == "month"
        assert client.delete(f"/api/saved-views/{view_id}").status_code == 409
        assert client.delete(f"/api/saved-views/{view_id}?confirmed=true").status_code == 200
        assert client.get(f"/api/saved-views/{view_id}").status_code == 404
    finally:
        client.delete(f"/api/saved-views/{view_id}?confirmed=true")


def test_saved_view_rejects_sensitive_fields() -> None:
    response = client.post("/api/saved-views", json={"name": "Unsafe", "source": "gsc", "config": {"filters": [], "oauthToken": "must-not-be-stored"}})
    assert response.status_code == 422
    assert "sensitive field" in response.json()["detail"]


def test_annotation_crud_and_scope_filtering() -> None:
    payload = {"date": "2026-07-03", "time": "09:30", "title": "Title update", "type": "content_update", "affectedUrl": "https://example.test/products/", "affectedQuery": "elecrest battery", "affectedPageGroup": "/products/", "notes": "Updated title and copy."}
    created = client.post("/api/annotations", json=payload)
    assert created.status_code == 200
    annotation_id = created.json()["id"]
    try:
        scoped = client.get("/api/annotations?start=2026-07-01&end=2026-07-04&query=elecrest%20battery&url=https%3A%2F%2Fexample.test%2Fproducts%2F").json()
        assert any(item["id"] == annotation_id for item in scoped)
        updated = client.put(f"/api/annotations/{annotation_id}", json={**payload, "title": "Updated annotation", "notes": "Verified note."})
        assert updated.status_code == 200
        assert updated.json()["title"] == "Updated annotation"
        assert client.delete(f"/api/annotations/{annotation_id}").status_code == 409
        assert client.delete(f"/api/annotations/{annotation_id}?confirmed=true").status_code == 200
    finally:
        client.delete(f"/api/annotations/{annotation_id}?confirmed=true")
