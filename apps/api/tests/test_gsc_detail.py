from __future__ import annotations

from fastapi.testclient import TestClient

from apps.api.main import app
from apps.api.services.analytics import _comparison_table, _opportunity_groups


client = TestClient(app)


def row(date: str, query: str, page: str, clicks: float, impressions: float, position: float) -> dict[str, str]:
    return {"date": date, "query": query, "page": page, "clicks": str(clicks), "impressions": str(impressions), "ctr": str(clicks / impressions if impressions else 0), "position": str(position)}


def test_comparison_groups_include_increased_declined_new_lost_and_near_first_page() -> None:
    current = [
        row("2026-07-10", "up", "/up", 5, 20, 5),
        row("2026-07-10", "down", "/down", 1, 20, 6),
        row("2026-07-10", "new", "/new", 2, 10, 15),
    ]
    previous = [
        row("2026-07-03", "up", "/up", 1, 20, 7),
        row("2026-07-03", "down", "/down", 4, 20, 5),
        row("2026-07-03", "lost", "/lost", 3, 15, 9),
    ]
    rows = _comparison_table(current, previous, "query", 0, True)
    groups = _opportunity_groups(rows, True)
    assert {item["label"] for item in groups["groups"]["increased"]} == {"up"}
    assert {item["label"] for item in groups["groups"]["declined"]} == {"down"}
    assert {item["label"] for item in groups["groups"]["new"]} == {"new"}
    assert {item["label"] for item in groups["groups"]["lost"]} == {"lost"}
    assert {item["label"] for item in groups["groups"]["nearFirstPage"]} == {"new"}
    lost = next(item for item in rows if item["label"] == "lost")
    assert lost["clicks"] == 0
    assert lost["previous_clicks"] == 3


def test_detail_endpoint_uses_exact_real_grain_and_disables_combined_dimensions() -> None:
    response = client.get("/api/gsc/detail", params={"entityType": "query", "value": "elecrest", "preset": "7", "comparison": "previous_period"})
    assert response.status_code == 200
    detail = response.json()
    assert detail["entityType"] == "query"
    assert detail["related"]["dimension"] == "page"
    assert detail["related"]["label"] == "Ranking Pages"
    assert detail["opportunities"]["status"] in {"available", "comparison_unavailable"}
    for name in ("country", "device", "searchAppearance"):
        assert detail["dimensionCapabilities"][name]["enabled"] is False
    assert any("date + query + page" in item for item in detail["limitations"])


def test_page_detail_and_invalid_entity_contract() -> None:
    page = client.get("/api/gsc/detail", params={"entityType": "page", "value": "https://www.elecrest.energy/", "preset": "7"})
    assert page.status_code == 200
    assert page.json()["related"]["dimension"] == "query"
    assert page.json()["related"]["label"] == "Query Portfolio"
    invalid = client.get("/api/gsc/detail", params={"entityType": "country", "value": "usa"})
    assert invalid.status_code == 422
