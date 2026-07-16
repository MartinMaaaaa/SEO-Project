"""Canonical PageSpeed Insights service for SEO-053."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
import datetime as dt
import ipaddress
import json
from pathlib import Path
import re
import threading
import time
from typing import Any, Callable
from urllib import error, parse, request

from apps.api.core.config import load_env
from apps.api.db import cloud_sync, pagespeed_store


API_URL = "https://www.googleapis.com/pagespeedonline/v5/runPagespeed"
DEFAULT_CATEGORIES = ("performance", "accessibility", "best-practices", "seo")
ALLOWED_CATEGORIES = frozenset(DEFAULT_CATEGORIES)
ALLOWED_STRATEGIES = frozenset(("mobile", "desktop"))
SAFE_LOCALES = re.compile(r"^[A-Za-z]{2,3}(?:-[A-Za-z0-9]{2,8})?$")
METRIC_IDS = (
    "first-contentful-paint",
    "largest-contentful-paint",
    "speed-index",
    "total-blocking-time",
    "cumulative-layout-shift",
)
_LOCKS: dict[tuple[str, str], threading.Lock] = {}
_LOCKS_GUARD = threading.Lock()


class PageSpeedError(RuntimeError):
    def __init__(self, code: str, message: str, *, http_status: int | None = None):
        super().__init__(message)
        self.code = code
        self.http_status = http_status
        self.safe_message = message[:500]


def normalize_public_url(value: str) -> str:
    raw = str(value or "").strip()
    if not raw:
        raise ValueError("URL is required.")
    if any(ord(char) < 32 or ord(char) == 127 for char in raw):
        raise ValueError("URL contains invalid control characters.")
    try:
        parts = parse.urlsplit(raw)
        port = parts.port
    except ValueError as exc:
        raise ValueError("URL contains an invalid host or port.") from exc
    scheme = parts.scheme.casefold()
    if scheme not in {"http", "https"}:
        raise ValueError("Only public http and https URLs are supported.")
    if parts.username is not None or parts.password is not None:
        raise ValueError("URLs containing credentials are not supported.")
    host = (parts.hostname or "").strip().rstrip(".").casefold()
    if not host:
        raise ValueError("URL must include a host.")
    try:
        ascii_host = host.encode("idna").decode("ascii")
    except UnicodeError as exc:
        raise ValueError("URL host is invalid.") from exc
    if ascii_host in {"localhost", "localhost.localdomain"} or ascii_host.endswith((".local", ".internal", ".localhost")):
        raise ValueError("URL must identify a public host.")
    try:
        address = ipaddress.ip_address(ascii_host)
    except ValueError:
        address = None
    if address is not None and not address.is_global:
        raise ValueError("URL must identify a public host.")
    default_port = (scheme == "http" and port == 80) or (scheme == "https" and port == 443)
    host_token = f"[{ascii_host}]" if ":" in ascii_host else ascii_host
    netloc = host_token if port is None or default_port else f"{host_token}:{port}"
    path = parts.path or "/"
    return parse.urlunsplit((scheme, netloc, path, parts.query, ""))


def validate_request(
    url: str,
    strategies: list[str] | tuple[str, ...] | None,
    categories: list[str] | tuple[str, ...] | None,
    locale: str,
) -> tuple[str, tuple[str, ...], tuple[str, ...], str]:
    normalized = normalize_public_url(url)
    requested_strategies = tuple(dict.fromkeys(str(item).casefold() for item in (strategies or ("mobile", "desktop"))))
    if not requested_strategies or any(item not in ALLOWED_STRATEGIES for item in requested_strategies):
        raise ValueError("strategies must contain mobile, desktop, or both.")
    requested_categories = tuple(dict.fromkeys(str(item).casefold() for item in (categories or DEFAULT_CATEGORIES)))
    if not requested_categories or any(item not in ALLOWED_CATEGORIES for item in requested_categories):
        raise ValueError("categories may contain only performance, accessibility, best-practices, and seo.")
    safe_locale = locale.strip() or "zh-CN"
    if not SAFE_LOCALES.fullmatch(safe_locale):
        raise ValueError("locale is invalid.")
    return normalized, requested_strategies, requested_categories, safe_locale


def _redact(value: object) -> str:
    text = str(value or "")
    key = load_env().get("PAGESPEED_API_KEY", "")
    if key:
        text = text.replace(key, "REDACTED")
    text = re.sub(r"(?i)([?&]key=)[^&\s]+", r"\1REDACTED", text)
    text = re.sub(r"(?i)(api[_ -]?key\s*[:=]\s*)[^\s,;]+", r"\1REDACTED", text)
    return text[:500]


def _fetch_json(
    normalized_url: str,
    strategy: str,
    categories: tuple[str, ...],
    locale: str,
    *,
    timeout: int = 125,
) -> dict[str, Any]:
    env = load_env()
    params: list[tuple[str, str]] = [("url", normalized_url), ("strategy", strategy), ("locale", locale)]
    params.extend(("category", category) for category in categories)
    api_key = env.get("PAGESPEED_API_KEY", "")
    if api_key:
        params.append(("key", api_key))
    endpoint = API_URL + "?" + parse.urlencode(params)
    req = request.Request(endpoint, headers={"Accept": "application/json"}, method="GET")
    try:
        with request.urlopen(req, timeout=timeout) as response:
            raw = response.read()
    except error.HTTPError as exc:
        details = exc.read().decode("utf-8", errors="replace")
        code = "rate_limited" if exc.code == 429 else "forbidden" if exc.code == 403 else "validation" if exc.code == 400 else "upstream_error"
        raise PageSpeedError(code, _redact(f"PageSpeed upstream returned HTTP {exc.code}. {details}"), http_status=exc.code) from exc
    except TimeoutError as exc:
        raise PageSpeedError("timeout", "PageSpeed request timed out.") from exc
    except error.URLError as exc:
        reason = str(getattr(exc, "reason", exc))
        code = "timeout" if "timed out" in reason.casefold() else "network_error"
        raise PageSpeedError(code, _redact(f"PageSpeed network request failed: {reason}")) from exc
    try:
        payload = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise PageSpeedError("invalid_response", "PageSpeed returned malformed JSON.") from exc
    if not isinstance(payload, dict):
        raise PageSpeedError("invalid_response", "PageSpeed response must be a JSON object.")
    return payload


def _nullable_number(value: object) -> float | int | None:
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return value
    try:
        return float(str(value))
    except (TypeError, ValueError):
        return None


def _score_percent(value: object) -> float | None:
    number = _nullable_number(value)
    return round(float(number) * 100, 2) if number is not None else None


def _safe_https_links(text: object) -> list[str]:
    links = re.findall(r"https://[^\s)\]>]+", str(text or ""))
    return list(dict.fromkeys(link.rstrip(".,;:") for link in links))[:8]


def _audit_summary(audit_id: str, audit: dict[str, Any]) -> dict[str, Any]:
    details = audit.get("details") if isinstance(audit.get("details"), dict) else None
    warnings = audit.get("warnings") if isinstance(audit.get("warnings"), list) else []
    return {
        "id": audit_id,
        "title": str(audit.get("title") or audit_id),
        "description": str(audit.get("description") or ""),
        "score": _nullable_number(audit.get("score")),
        "scoreDisplayMode": str(audit.get("scoreDisplayMode") or ""),
        "displayValue": audit.get("displayValue"),
        "numericValue": _nullable_number(audit.get("numericValue")),
        "numericUnit": audit.get("numericUnit"),
        "metricSavings": audit.get("metricSavings") if isinstance(audit.get("metricSavings"), dict) else None,
        "warnings": warnings,
        "details": details,
        "documentationLinks": _safe_https_links(audit.get("description")),
    }


def parse_response(
    payload: dict[str, Any],
    *,
    normalized_url: str,
    strategy: str,
    locale: str,
    categories_requested: tuple[str, ...] = DEFAULT_CATEGORIES,
) -> dict[str, Any]:
    lighthouse = payload.get("lighthouseResult")
    if not isinstance(lighthouse, dict):
        raise PageSpeedError("invalid_response", "PageSpeed response is missing lighthouseResult.")
    runtime_error = lighthouse.get("runtimeError")
    if isinstance(runtime_error, dict) and runtime_error:
        code = str(runtime_error.get("code") or "runtime_error")
        message = _redact(runtime_error.get("message") or "Lighthouse could not complete the run.")
        runtime_text = (code + " " + message).casefold()
        error_code = "timeout" if "timeout" in runtime_text or "timed out" in runtime_text else "runtime_error"
        raise PageSpeedError(error_code, message)
    categories_raw = lighthouse.get("categories")
    audits_raw = lighthouse.get("audits")
    if not isinstance(categories_raw, dict) or not isinstance(audits_raw, dict):
        raise PageSpeedError("invalid_response", "PageSpeed response is missing Lighthouse categories or audits.")
    category_groups = lighthouse.get("categoryGroups") if isinstance(lighthouse.get("categoryGroups"), dict) else {}
    categories: dict[str, Any] = {}
    referenced: dict[str, list[dict[str, Any]]] = {}
    for category_id, category in categories_raw.items():
        if not isinstance(category, dict):
            continue
        refs = []
        for ref in category.get("auditRefs", []) if isinstance(category.get("auditRefs"), list) else []:
            if not isinstance(ref, dict) or not ref.get("id"):
                continue
            refs.append({
                "id": str(ref["id"]),
                "weight": _nullable_number(ref.get("weight")),
                "group": ref.get("group"),
                "acronym": ref.get("acronym"),
            })
        referenced[str(category_id)] = refs
        categories[str(category_id)] = {
            "id": str(category_id),
            "title": category.get("title"),
            "description": category.get("description"),
            "score": _score_percent(category.get("score")),
            "auditRefs": refs,
        }
    audits = {str(audit_id): _audit_summary(str(audit_id), audit) for audit_id, audit in audits_raw.items() if isinstance(audit, dict)}
    metrics = {metric_id: audits.get(metric_id) for metric_id in METRIC_IDS if metric_id in audits}
    missing_categories = [category for category in categories_requested if category not in categories]
    loading = payload.get("loadingExperience") if isinstance(payload.get("loadingExperience"), dict) else None
    origin_loading = payload.get("originLoadingExperience") if isinstance(payload.get("originLoadingExperience"), dict) else None
    limitations = [
        "Lighthouse is a controlled lab test and can vary between runs.",
        "Total Blocking Time is a lab diagnostic proxy; it is not a measured INP value.",
        "Source-returned guidance is evidence, not proof of ranking, conversion, or business impact.",
    ]
    if missing_categories:
        limitations.append("The upstream response omitted categories: " + ", ".join(missing_categories) + ".")
    requested_url = str(lighthouse.get("requestedUrl") or payload.get("id") or normalized_url)
    final_url = str(lighthouse.get("finalDisplayedUrl") or lighthouse.get("finalUrl") or requested_url)
    return {
        "schemaVersion": pagespeed_store.SCHEMA_VERSION,
        "status": "success",
        "urlKey": normalized_url,
        "requestedUrl": requested_url,
        "finalUrl": final_url,
        "strategy": strategy,
        "locale": str(lighthouse.get("configSettings", {}).get("locale") or locale) if isinstance(lighthouse.get("configSettings"), dict) else locale,
        "fetchTime": lighthouse.get("fetchTime"),
        "savedAt": None,
        "lighthouseVersion": lighthouse.get("lighthouseVersion"),
        "categories": categories,
        "categoryAuditRefs": referenced,
        "categoryGroups": category_groups,
        "audits": audits,
        "metrics": metrics,
        "environment": lighthouse.get("environment") if isinstance(lighthouse.get("environment"), dict) else {},
        "configSettings": lighthouse.get("configSettings") if isinstance(lighthouse.get("configSettings"), dict) else {},
        "runWarnings": lighthouse.get("runWarnings") if isinstance(lighthouse.get("runWarnings"), list) else [],
        "runtimeError": None,
        "fullPageScreenshot": lighthouse.get("fullPageScreenshot") if isinstance(lighthouse.get("fullPageScreenshot"), dict) else None,
        "timing": lighthouse.get("timing") if isinstance(lighthouse.get("timing"), dict) else {},
        "entities": lighthouse.get("entities") if isinstance(lighthouse.get("entities"), list) else [],
        "psiFieldData": {
            "source": "PageSpeed Insights loadingExperience (transitional)",
            "loadingExperience": loading,
            "originLoadingExperience": origin_loading,
        } if loading or origin_loading else None,
        "limitations": limitations,
        "persistence": {"local": "pending", "cloud": {"ok": False, "skipped": True}},
    }


def _key_lock(url_key: str, strategy: str) -> threading.Lock:
    with _LOCKS_GUARD:
        return _LOCKS.setdefault((url_key, strategy), threading.Lock())


def _run_one(
    url_key: str,
    strategy: str,
    categories: tuple[str, ...],
    locale: str,
    *,
    fetcher: Callable[[str, str, tuple[str, ...], str], dict[str, Any]] | None = None,
) -> dict[str, Any]:
    lock = _key_lock(url_key, strategy)
    if not lock.acquire(blocking=False):
        return {"ok": False, "strategy": strategy, "error": {"code": "in_progress", "message": "This URL and device are already being tested."}}
    started = dt.datetime.now(dt.timezone.utc)
    pagespeed_store.record_attempt(url_key=url_key, requested_url=url_key, strategy=strategy, status="running", started_at=started.isoformat())
    try:
        try:
            payload = (fetcher or _fetch_json)(url_key, strategy, categories, locale)
            result = parse_response(payload, normalized_url=url_key, strategy=strategy, locale=locale, categories_requested=categories)
            try:
                stored = pagespeed_store.persist_success(result, payload)
            except Exception as exc:
                raise PageSpeedError("persistence_error", _redact(f"Local PageSpeed persistence failed: {type(exc).__name__}")) from exc
            cloud: dict[str, Any] = {"ok": False, "skipped": True}
            if cloud_sync.is_supabase_configured():
                try:
                    cloud = cloud_sync.upload_pagespeed_latest_result(stored, pagespeed_store.active_file_path(url_key, strategy))
                except Exception as exc:  # noqa: BLE001
                    cloud = {"ok": False, "skipped": False, "degraded": True, "errorType": type(exc).__name__}
            completed = dt.datetime.now(dt.timezone.utc)
            duration = int((completed - started).total_seconds() * 1000)
            stored["persistence"] = {"local": "saved", "cloud": cloud}
            pagespeed_store.update_result_persistence(url_key, strategy, stored["persistence"])
            pagespeed_store.record_attempt(
                url_key=url_key, requested_url=url_key, strategy=strategy, status="success",
                started_at=started.isoformat(), completed_at=completed.isoformat(), duration_ms=duration,
                persistence_status="saved", cloud_status=cloud,
            )
            stored["latestAttempt"] = {
                "status": "success", "startedAt": started.isoformat(), "completedAt": completed.isoformat(),
                "durationMs": duration, "persistenceStatus": "saved", "cloud": cloud,
            }
            return {"ok": True, "strategy": strategy, "result": stored}
        except PageSpeedError as exc:
            completed = dt.datetime.now(dt.timezone.utc)
            duration = int((completed - started).total_seconds() * 1000)
            pagespeed_store.record_attempt(
                url_key=url_key, requested_url=url_key, strategy=strategy, status="failed",
                started_at=started.isoformat(), completed_at=completed.isoformat(), duration_ms=duration,
                error_code=exc.code, error_message=_redact(exc.safe_message), http_status=exc.http_status,
                persistence_status="not_saved",
            )
            return {"ok": False, "strategy": strategy, "error": {"code": exc.code, "message": _redact(exc.safe_message), "httpStatus": exc.http_status}, "durationMs": duration}
    finally:
        lock.release()


def analyze(
    url: str,
    strategies: list[str] | tuple[str, ...] | None = None,
    categories: list[str] | tuple[str, ...] | None = None,
    locale: str = "zh-CN",
    *,
    fetcher: Callable[[str, str, tuple[str, ...], str], dict[str, Any]] | None = None,
) -> dict[str, Any]:
    normalized, devices, requested_categories, safe_locale = validate_request(url, strategies, categories, locale)
    results: dict[str, Any] = {}
    with ThreadPoolExecutor(max_workers=min(2, len(devices))) as executor:
        futures = {executor.submit(_run_one, normalized, strategy, requested_categories, safe_locale, fetcher=fetcher): strategy for strategy in devices}
        for future in as_completed(futures):
            strategy = futures[future]
            try:
                results[strategy] = future.result()
            except Exception as exc:  # noqa: BLE001
                results[strategy] = {"ok": False, "strategy": strategy, "error": {"code": "internal_error", "message": _redact(type(exc).__name__)}}
    successes = sum(1 for item in results.values() if item.get("ok"))
    status = "success" if successes == len(devices) else "partial" if successes else "error"
    return {"ok": status == "success", "status": status, "normalizedUrl": normalized, "strategies": list(devices), "categories": list(requested_categories), "locale": safe_locale, "results": results}


def latest(url: str = "", strategy: str = "") -> dict[str, Any]:
    url_key = normalize_public_url(url) if url else ""
    if strategy and strategy not in ALLOWED_STRATEGIES:
        raise ValueError("strategy must be mobile or desktop.")
    results = pagespeed_store.latest_results(url_key, strategy)
    return {
        "status": "ok" if results else "no_data",
        "schemaVersion": pagespeed_store.SCHEMA_VERSION,
        "normalizedUrl": url_key or None,
        "results": results,
        "counts": pagespeed_store.counts(),
        "metadata": {
            "retention": "latest successful result only per normalized URL and strategy",
            "cachedReadCallsGoogle": False,
            "failureSemantics": "A failed attempt never replaces the latest successful result and never becomes score 0.",
        },
    }


def compatibility_history(url: str = "", strategy: str = "") -> dict[str, Any]:
    """Latest-only response shape retained for existing overview consumers."""

    body = latest(url, strategy)
    runs = body["results"]
    return {
        **body,
        "runs": runs,
        "latest": runs,
        "pages": [],
        "sqliteRuns": [],
    }


def raw_evidence(url: str, strategy: str) -> dict[str, Any]:
    url_key = normalize_public_url(url)
    if strategy not in ALLOWED_STRATEGIES:
        raise ValueError("strategy must be mobile or desktop.")
    payload = pagespeed_store.read_raw(url_key, strategy)
    if not payload:
        raise FileNotFoundError("No active raw payload exists for this URL and strategy.")
    return payload


def compact_legacy_history() -> dict[str, Any]:
    """Back up and compact timestamped legacy PageSpeed files exactly once."""

    raw_dir = pagespeed_store.RAW_DIR
    legacy = sorted(path for path in raw_dir.glob("pagespeed_*.json") if not path.name.startswith("pagespeed_active_")) if raw_dir.exists() else []
    if not legacy:
        return {"ok": True, "status": "already_compact", **pagespeed_store.counts(), "legacyFilesRemoved": 0, "legacyRowsRemoved": 0, "backup": None}
    backup_paths = [pagespeed_store.DB_PATH, *legacy]
    backup = cloud_sync.make_backup(backup_paths, "pagespeed_latest_compaction")
    selected: dict[tuple[str, str], tuple[str, float, dict[str, Any], dict[str, Any]]] = {}
    failures: dict[tuple[str, str], tuple[float, str]] = {}
    invalid = 0
    for path in legacy:
        try:
            wrapper = json.loads(path.read_text(encoding="utf-8"))
            response = wrapper.get("response") if isinstance(wrapper, dict) and isinstance(wrapper.get("response"), dict) else wrapper
            summary = wrapper.get("summary", {}) if isinstance(wrapper, dict) and isinstance(wrapper.get("summary"), dict) else {}
            match = re.search(r"_(mobile|desktop)_\d{8}_\d{6}\.json$", path.name)
            strategy = match.group(1) if match else str(response.get("lighthouseResult", {}).get("configSettings", {}).get("formFactor") or "")
            if strategy not in ALLOWED_STRATEGIES:
                invalid += 1
                continue
            requested_url = str(summary.get("requestedUrl") or response.get("lighthouseResult", {}).get("requestedUrl") or response.get("id") or "")
            url_key = normalize_public_url(requested_url)
            try:
                result = parse_response(response, normalized_url=url_key, strategy=strategy, locale="zh-CN")
            except PageSpeedError as exc:
                failures[(url_key, strategy)] = max(failures.get((url_key, strategy), (0.0, "")), (path.stat().st_mtime, exc.code))
                continue
            fetched = str(result.get("fetchTime") or "")
            try:
                order = dt.datetime.fromisoformat(fetched.replace("Z", "+00:00")).timestamp()
            except ValueError:
                order = path.stat().st_mtime
            key = (url_key, strategy)
            if key not in selected or order > selected[key][1]:
                selected[key] = (fetched, order, result, response)
        except (OSError, ValueError, json.JSONDecodeError, TypeError):
            invalid += 1
    for (url_key, strategy), (_, _, result, response) in selected.items():
        result["persistence"] = {"local": "migrated", "cloud": {"ok": False, "skipped": True}}
        stored = pagespeed_store.persist_success(result, response)
        pagespeed_store.record_attempt(
            url_key=url_key, requested_url=url_key, strategy=strategy, status="success",
            started_at=str(stored.get("savedAt") or dt.datetime.now(dt.timezone.utc).isoformat()),
            completed_at=str(stored.get("savedAt") or dt.datetime.now(dt.timezone.utc).isoformat()),
            duration_ms=0, persistence_status="migrated", cloud_status={"ok": False, "skipped": True},
        )
    for key, (order, code) in failures.items():
        success_order = selected.get(key, ("", 0.0, {}, {}))[1]
        if order > success_order:
            url_key, strategy = key
            pagespeed_store.record_attempt(
                url_key=url_key, requested_url=url_key, strategy=strategy, status="failed",
                started_at=dt.datetime.fromtimestamp(order, dt.timezone.utc).isoformat(),
                completed_at=dt.datetime.fromtimestamp(order, dt.timezone.utc).isoformat(),
                duration_ms=0, error_code=code, error_message="Legacy latest attempt failed; successful active result was preserved.",
                persistence_status="not_saved",
            )
    legacy_rows = pagespeed_store.clear_legacy_rows()
    removed = 0
    root = raw_dir.resolve()
    for path in legacy:
        resolved = path.resolve()
        if resolved.parent != root:
            raise RuntimeError("Refusing to remove a legacy file outside the PageSpeed raw directory.")
        resolved.unlink()
        removed += 1
    return {
        "ok": True,
        "status": "compacted",
        **pagespeed_store.counts(),
        "legacyFilesRemoved": removed,
        "legacyRowsRemoved": legacy_rows,
        "invalidLegacyFiles": invalid,
        "selectedKeys": len(selected),
        "backup": {"backupId": backup["backupId"], "backupPath": backup["backupPath"], "files": len(backup["manifest"]["files"])},
    }
