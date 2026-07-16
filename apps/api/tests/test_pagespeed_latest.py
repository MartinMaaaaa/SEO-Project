from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from apps.api.db import cloud_sync, pagespeed_store
from apps.api.services import analytics, pagespeed_service


def payload(url: str, strategy: str, *, performance: float | None = 0.8, fetched: str = "2026-07-16T00:00:00.000Z") -> dict[str, Any]:
    return {
        "id": url,
        "loadingExperience": {"initial_url": url},
        "lighthouseResult": {
            "requestedUrl": url,
            "finalDisplayedUrl": url,
            "fetchTime": fetched,
            "lighthouseVersion": "13.test",
            "configSettings": {"locale": "zh-CN", "formFactor": strategy},
            "environment": {"benchmarkIndex": 1000},
            "runWarnings": [],
            "categoryGroups": {"metrics": {"title": "Metrics"}},
            "categories": {
                "performance": {"title": "Performance", "score": performance, "auditRefs": [{"id": "first-contentful-paint", "weight": 10, "group": "metrics"}]},
                "accessibility": {"title": "Accessibility", "score": None, "auditRefs": [{"id": "color-contrast", "weight": 3}]},
                "best-practices": {"title": "Best Practices", "score": 0.9, "auditRefs": []},
                "seo": {"title": "SEO", "score": 1, "auditRefs": []},
            },
            "audits": {
                "first-contentful-paint": {"title": "First Contentful Paint", "score": performance, "scoreDisplayMode": "numeric", "displayValue": "1.2 s", "numericValue": 1200, "numericUnit": "millisecond"},
                "color-contrast": {"title": "Background and foreground colors", "description": "See https://developer.chrome.com/docs/lighthouse/accessibility/color-contrast/", "score": None, "scoreDisplayMode": "manual", "details": {"type": "table", "headings": [{"key": "node", "label": "Node"}], "items": []}},
                "unused-javascript": {"title": "Reduce unused JavaScript", "score": 0.4, "scoreDisplayMode": "metricSavings", "details": {"type": "opportunity", "overallSavingsMs": 300, "overallSavingsBytes": 2048, "headings": [], "items": []}},
            },
            "fullPageScreenshot": {"screenshot": {"data": "data:image/jpeg;base64,AA=="}},
            "timing": {"total": 1000},
        },
    }


@pytest.fixture()
def isolated_store(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Path, Path]:
    db = tmp_path / "local" / "seo.sqlite"
    raw = tmp_path / "pagespeed" / "raw"
    monkeypatch.setattr(pagespeed_store, "DB_PATH", db)
    monkeypatch.setattr(pagespeed_store, "RAW_DIR", raw)
    monkeypatch.setattr(cloud_sync, "is_supabase_configured", lambda: False)
    return db, raw


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("HTTPS://Example.COM:443/path?q=1#fragment", "https://example.com/path?q=1"),
        ("http://Example.com:80", "http://example.com/"),
        ("https://example.com/A/?b=2&a=1", "https://example.com/A/?b=2&a=1"),
    ],
)
def test_url_normalization(raw: str, expected: str) -> None:
    assert pagespeed_service.normalize_public_url(raw) == expected


@pytest.mark.parametrize("raw", ["", "ftp://example.com", "https://user:pass@example.com", "http://127.0.0.1", "http://localhost", "javascript:alert(1)"])
def test_invalid_or_non_public_urls_are_rejected(raw: str) -> None:
    with pytest.raises(ValueError):
        pagespeed_service.normalize_public_url(raw)


def test_parse_preserves_four_categories_nulls_and_complete_audit_shapes() -> None:
    result = pagespeed_service.parse_response(payload("https://example.com/", "mobile"), normalized_url="https://example.com/", strategy="mobile", locale="zh-CN")
    assert set(result["categories"]) == set(pagespeed_service.DEFAULT_CATEGORIES)
    assert result["categories"]["performance"]["score"] == 80
    assert result["categories"]["accessibility"]["score"] is None
    assert result["audits"]["color-contrast"]["score"] is None
    assert result["audits"]["color-contrast"]["details"]["type"] == "table"
    assert result["audits"]["unused-javascript"]["details"]["overallSavingsMs"] == 300
    assert result["metrics"]["first-contentful-paint"]["numericValue"] == 1200
    assert "interaction-to-next-paint" not in result["metrics"]
    assert result["fullPageScreenshot"] is not None


def test_runtime_error_is_not_a_zero_score() -> None:
    body = payload("https://example.com/", "mobile")
    body["lighthouseResult"]["runtimeError"] = {"code": "ERRORED_DOCUMENT_REQUEST", "message": "The page timed out."}
    with pytest.raises(pagespeed_service.PageSpeedError) as exc:
        pagespeed_service.parse_response(body, normalized_url="https://example.com/", strategy="mobile", locale="zh-CN")
    assert exc.value.code == "timeout"


def test_mobile_desktop_retests_replace_two_active_rows_and_files(isolated_store: tuple[Path, Path]) -> None:
    calls: list[tuple[str, tuple[str, ...]]] = []

    def fetch(url: str, strategy: str, categories: tuple[str, ...], locale: str) -> dict[str, Any]:
        del locale
        calls.append((strategy, categories))
        return payload(url, strategy, performance=0.8 if strategy == "mobile" else 0.9)

    first = pagespeed_service.analyze("https://Example.com:443/#x", ["mobile", "desktop"], fetcher=fetch)
    assert first["status"] == "success"
    assert pagespeed_store.counts() == {"activeRows": 2, "activeRawFiles": 2, "latestAttempts": 2}
    assert all(categories == pagespeed_service.DEFAULT_CATEGORIES for _, categories in calls)
    second = pagespeed_service.analyze("https://example.com/", ["mobile", "desktop"], fetcher=fetch)
    assert second["status"] == "success"
    assert pagespeed_store.counts() == {"activeRows": 2, "activeRawFiles": 2, "latestAttempts": 2}
    latest = pagespeed_service.latest("https://example.com/")
    assert len(latest["results"]) == 2
    assert all(item["latestAttempt"]["status"] == "success" for item in latest["results"])


def test_two_pages_by_two_devices_keep_at_most_four(isolated_store: tuple[Path, Path]) -> None:
    def fetch(url: str, strategy: str, categories: tuple[str, ...], locale: str) -> dict[str, Any]:
        del categories, locale
        return payload(url, strategy)

    for url in ("https://example.com/a", "https://example.com/b"):
        assert pagespeed_service.analyze(url, ["mobile", "desktop"], fetcher=fetch)["status"] == "success"
    assert pagespeed_store.counts()["activeRows"] == 4
    assert pagespeed_store.counts()["activeRawFiles"] == 4


@pytest.mark.parametrize("code", ["validation", "timeout", "rate_limited", "forbidden", "upstream_error", "runtime_error", "invalid_response"])
def test_device_errors_are_classified_and_preserve_previous_success(isolated_store: tuple[Path, Path], code: str) -> None:
    def success(url: str, strategy: str, categories: tuple[str, ...], locale: str) -> dict[str, Any]:
        del categories, locale
        return payload(url, strategy, performance=0.77)

    assert pagespeed_service.analyze("https://example.com/", ["mobile"], fetcher=success)["status"] == "success"
    before = pagespeed_service.latest("https://example.com/", "mobile")["results"][0]

    def failure(url: str, strategy: str, categories: tuple[str, ...], locale: str) -> dict[str, Any]:
        del url, strategy, categories, locale
        raise pagespeed_service.PageSpeedError(code, "safe failure", http_status=429 if code == "rate_limited" else None)

    failed = pagespeed_service.analyze("https://example.com/", ["mobile"], fetcher=failure)
    assert failed["status"] == "error"
    after = pagespeed_service.latest("https://example.com/", "mobile")["results"][0]
    assert after["categories"] == before["categories"]
    assert after["latestAttempt"]["status"] == "failed"
    assert after["latestAttempt"]["errorCode"] == code
    assert pagespeed_store.counts()["activeRows"] == 1
    assert pagespeed_store.counts()["activeRawFiles"] == 1


def test_persistence_failure_is_device_specific_and_not_reported_as_success(isolated_store: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch) -> None:
    def fetch(url: str, strategy: str, categories: tuple[str, ...], locale: str) -> dict[str, Any]:
        del categories, locale
        return payload(url, strategy)

    monkeypatch.setattr(pagespeed_store, "persist_success", lambda *args, **kwargs: (_ for _ in ()).throw(OSError("disk failed")))
    result = pagespeed_service.analyze("https://example.com/", ["mobile"], fetcher=fetch)
    assert result["results"]["mobile"]["error"]["code"] == "persistence_error"
    assert pagespeed_store.counts()["activeRows"] == 0


def test_cached_latest_and_raw_reads_do_not_call_google(isolated_store: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch) -> None:
    stored = pagespeed_service.parse_response(payload("https://example.com/", "desktop"), normalized_url="https://example.com/", strategy="desktop", locale="en")
    pagespeed_store.persist_success(stored, payload("https://example.com/", "desktop"))
    monkeypatch.setattr(pagespeed_service, "_fetch_json", lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("Google call")))
    assert pagespeed_service.latest("https://example.com/")["results"][0]["strategy"] == "desktop"
    assert pagespeed_service.raw_evidence("https://example.com/", "desktop")["response"]["lighthouseResult"]


def test_secret_redaction() -> None:
    text = pagespeed_service._redact("request failed?key=very-secret-value api_key=another-secret")
    assert "very-secret-value" not in text
    assert "another-secret" not in text
    assert text.count("REDACTED") == 2


def test_migration_backs_up_compacts_and_is_idempotent(isolated_store: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch) -> None:
    db, raw = isolated_store
    raw.mkdir(parents=True)
    older = raw / "pagespeed_example_mobile_20260715_010101.json"
    newer = raw / "pagespeed_example_mobile_20260716_010101.json"
    desktop = raw / "pagespeed_example_desktop_20260716_010102.json"
    older.write_text(json.dumps({"summary": {"requestedUrl": "https://example.com/"}, "response": payload("https://example.com/", "mobile", performance=0.5, fetched="2026-07-15T00:00:00Z")}), encoding="utf-8")
    newer.write_text(json.dumps({"summary": {"requestedUrl": "https://example.com/"}, "response": payload("https://example.com/", "mobile", performance=0.8, fetched="2026-07-16T00:00:00Z")}), encoding="utf-8")
    desktop.write_text(json.dumps({"summary": {"requestedUrl": "https://example.com/"}, "response": payload("https://example.com/", "desktop", performance=0.9, fetched="2026-07-16T00:00:01Z")}), encoding="utf-8")
    with pagespeed_store.connect(db) as conn:
        conn.execute("CREATE TABLE pagespeed_runs (id INTEGER PRIMARY KEY, url TEXT, strategy TEXT)")
        conn.execute("INSERT INTO pagespeed_runs (url, strategy) VALUES ('x','mobile'),('x','mobile')")
        conn.commit()
    backups: list[list[Path]] = []

    def backup(paths: list[Path], label: str) -> dict[str, Any]:
        backups.append(paths)
        return {"backupId": "test-backup", "backupPath": "data/backups/test", "manifest": {"files": [{"path": str(path)} for path in paths]}, "label": label}

    monkeypatch.setattr(cloud_sync, "make_backup", backup)
    first = pagespeed_service.compact_legacy_history()
    assert first["status"] == "compacted"
    assert first["activeRows"] == 2 and first["activeRawFiles"] == 2
    assert first["legacyFilesRemoved"] == 3 and first["legacyRowsRemoved"] == 2
    assert backups and db in backups[0]
    second = pagespeed_service.compact_legacy_history()
    assert second["status"] == "already_compact"
    assert second["activeRows"] == 2 and second["activeRawFiles"] == 2


def test_supabase_latest_uses_active_key_upsert(tmp_path: Path) -> None:
    class Cursor:
        sql = ""
        params: tuple[Any, ...] = ()

        def execute(self, sql: str, params: tuple[Any, ...]) -> None:
            self.sql = sql
            self.params = params

    raw = tmp_path / "active.json"
    raw.write_text("{}", encoding="utf-8")
    cursor = Cursor()
    result = {"urlKey": "https://example.com/", "requestedUrl": "https://example.com/", "finalUrl": "https://example.com/", "strategy": "mobile", "fetchTime": "2026-07-16T00:00:00Z", "savedAt": "2026-07-16T00:01:00Z", "lighthouseVersion": "13", "locale": "en"}
    cloud_sync.upsert_pagespeed_latest_cursor(cursor, result, raw)
    assert "ON CONFLICT (active_key) DO UPDATE" in cursor.sql
    assert cursor.params[1] == "https://example.com/"
    assert cursor.params[4] == "mobile"


def test_crux_page_origin_fallback_and_no_dataset(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    crux = tmp_path / "crux"
    crux.mkdir()
    monkeypatch.setitem(analytics.RAW, "crux", crux)
    monkeypatch.setattr(analytics, "latest_api_run", lambda source: None)
    assert analytics.summarize_crux("https://example.com/page")["status"] == "no_data"
    origin_summary = {"summary": {"key": {"origin": "https://example.com"}, "collectionPeriod": {"firstDate": {}, "lastDate": {}}, "metrics": {"largest_contentful_paint": {"p75": 2000, "histogram": []}}}}
    (crux / "crux_origin_example_PHONE_20260716_000000.json").write_text(json.dumps(origin_summary), encoding="utf-8")
    fallback = analytics.summarize_crux("https://example.com/page", "PHONE")
    assert fallback["scope"] == "origin" and fallback["originFallback"] is True
    page_summary = {"summary": {"key": {"url": "https://example.com/page"}, "collectionPeriod": {}, "metrics": {}}}
    (crux / "crux_url_example_PHONE_20260716_000001.json").write_text(json.dumps(page_summary), encoding="utf-8")
    page = analytics.summarize_crux("https://example.com/page", "PHONE")
    assert page["scope"] == "page" and page["originFallback"] is False
