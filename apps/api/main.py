from __future__ import annotations

import datetime as dt
import mimetypes
import os
from pathlib import Path
import threading
from typing import Any

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from apps.api.core.config import masked_env, settings
from apps.api.db import analysis_store
from apps.api.services import analytics, pagespeed_service, storage_service


class PageSpeedSyncRequest(BaseModel):
    url: str = ""
    strategy: str = "mobile"


class PageSpeedAnalyzeRequest(BaseModel):
    url: str
    strategies: list[str] = Field(default_factory=lambda: ["mobile", "desktop"])
    categories: list[str] = Field(default_factory=lambda: list(pagespeed_service.DEFAULT_CATEGORIES))
    locale: str = "zh-CN"


class SourceSyncRequest(BaseModel):
    force: bool = False


class AiTaskRequest(BaseModel):
    taskType: str = "seo_analysis"
    title: str = "Scoped SEO analysis"
    scope: dict[str, Any] = Field(default_factory=dict)
    evidence: dict[str, Any] = Field(default_factory=dict)


class SavedViewRequest(BaseModel):
    name: str
    description: str = ""
    source: str = "gsc"
    isFavorite: bool = False
    config: dict[str, Any] = Field(default_factory=dict)


class AnnotationRequest(BaseModel):
    date: str
    time: str = ""
    title: str
    type: str = "note"
    affectedUrl: str = ""
    affectedQuery: str = ""
    affectedPageGroup: str = ""
    notes: str = ""


def create_app() -> FastAPI:
    cfg = settings()
    app = FastAPI(title=cfg.app_name, version="0.2.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://127.0.0.1:5173", "http://localhost:5173"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/api/health")
    def health() -> dict[str, Any]:
        return {
            "ok": True,
            "time": dt.datetime.now().isoformat(timespec="seconds"),
            "architecture": storage_service.architecture(),
            "databaseMode": cfg.database_mode,
        }

    @app.get("/api/architecture")
    def architecture() -> dict[str, Any]:
        return storage_service.architecture()

    @app.get("/api/status")
    def status() -> dict[str, Any]:
        return {"env": masked_env(), **analytics.status()}

    @app.get("/api/storage/overview")
    def storage_overview() -> dict[str, Any]:
        return storage_service.overview()

    @app.get("/api/gsc/explorer")
    def gsc_explorer(
        query: str = "",
        page: str = "",
        start: str = "",
        end: str = "",
        minImpressions: float = 0,
        sort: str = "clicks",
        preset: str = "28",
        comparison: str = "previous_period",
        grain: str = "day",
        filters: str = "",
        limit: int = Query(default=50, ge=1, le=200),
    ) -> dict[str, Any]:
        return analytics.gsc_explorer(
            {
                "query": [query],
                "page": [page],
                "start": [start],
                "end": [end],
                "minImpressions": [str(minImpressions)],
                "sort": [sort],
                "limit": [str(limit)],
                "preset": [preset],
                "comparison": [comparison],
                "grain": [grain],
                "filters": [filters],
            }
        )

    @app.get("/api/gsc/detail")
    def gsc_detail(
        entityType: str,
        value: str,
        start: str = "",
        end: str = "",
        preset: str = "28",
        comparison: str = "previous_period",
        grain: str = "day",
        limit: int = Query(default=100, ge=1, le=200),
    ) -> dict[str, Any]:
        if entityType not in {"query", "page"}:
            raise HTTPException(status_code=422, detail="entityType must be query or page")
        return analytics.gsc_detail(entityType, value, {"start": [start], "end": [end], "preset": [preset], "comparison": [comparison], "grain": [grain], "limit": [str(limit)], "sort": ["clicks"]})

    @app.get("/api/ga4/analytics")
    def ga4_analytics(channel: str = "") -> dict[str, Any]:
        return analytics.ga4_analytics({"channel": [channel]})

    @app.get("/api/pagespeed/history")
    def pagespeed_history(url: str = "", strategy: str = "") -> dict[str, Any]:
        try:
            return pagespeed_service.compatibility_history(url, strategy)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    @app.get("/api/pagespeed/latest")
    def pagespeed_latest(url: str = "", strategy: str = "") -> dict[str, Any]:
        try:
            return pagespeed_service.latest(url, strategy)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    @app.get("/api/pagespeed/raw")
    def pagespeed_raw(url: str, strategy: str) -> dict[str, Any]:
        try:
            return pagespeed_service.raw_evidence(url, strategy)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.get("/api/crux/summary")
    def crux_summary(url: str = "", formFactor: str = "") -> dict[str, Any]:
        try:
            return analytics.summarize_crux(url, formFactor)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    @app.get("/api/ai/tasks")
    def ai_tasks(limit: int = Query(default=30, ge=1, le=100)) -> list[dict[str, Any]]:
        return analytics.recent_ai_tasks(limit)

    @app.post("/api/ai/tasks")
    def create_ai_task(payload: AiTaskRequest) -> dict[str, Any]:
        return analytics.generate_ai_task(payload.model_dump())

    @app.get("/api/saved-views")
    def saved_views(source: str = "") -> list[dict[str, Any]]:
        return analysis_store.list_saved_views(source)

    @app.get("/api/saved-views/{view_id}")
    def saved_view(view_id: int) -> dict[str, Any]:
        result = analysis_store.get_saved_view(view_id)
        if not result:
            raise HTTPException(status_code=404, detail="Saved view not found")
        return result

    @app.post("/api/saved-views")
    def create_saved_view(payload: SavedViewRequest) -> dict[str, Any]:
        try:
            return analysis_store.create_saved_view(payload.model_dump())
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    @app.put("/api/saved-views/{view_id}")
    def update_saved_view(view_id: int, payload: SavedViewRequest) -> dict[str, Any]:
        try:
            result = analysis_store.update_saved_view(view_id, payload.model_dump())
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        if not result:
            raise HTTPException(status_code=404, detail="Saved view not found")
        return result

    @app.delete("/api/saved-views/{view_id}")
    def delete_saved_view(view_id: int, confirmed: bool = False) -> dict[str, Any]:
        if not confirmed:
            raise HTTPException(status_code=409, detail="Deletion requires confirmed=true")
        if not analysis_store.delete_saved_view(view_id):
            raise HTTPException(status_code=404, detail="Saved view not found")
        return {"ok": True, "id": view_id}

    @app.get("/api/annotations")
    def annotations(start: str = "", end: str = "", query: str = "", url: str = "") -> list[dict[str, Any]]:
        return analysis_store.list_annotations(start, end, query, url)

    @app.get("/api/annotations/{annotation_id}")
    def annotation(annotation_id: int) -> dict[str, Any]:
        result = analysis_store.get_annotation(annotation_id)
        if not result:
            raise HTTPException(status_code=404, detail="Annotation not found")
        return result

    @app.post("/api/annotations")
    def create_annotation(payload: AnnotationRequest) -> dict[str, Any]:
        return analysis_store.create_annotation(payload.model_dump())

    @app.put("/api/annotations/{annotation_id}")
    def update_annotation(annotation_id: int, payload: AnnotationRequest) -> dict[str, Any]:
        result = analysis_store.update_annotation(annotation_id, payload.model_dump())
        if not result:
            raise HTTPException(status_code=404, detail="Annotation not found")
        return result

    @app.delete("/api/annotations/{annotation_id}")
    def delete_annotation(annotation_id: int, confirmed: bool = False) -> dict[str, Any]:
        if not confirmed:
            raise HTTPException(status_code=409, detail="Deletion requires confirmed=true")
        if not analysis_store.delete_annotation(annotation_id):
            raise HTTPException(status_code=404, detail="Annotation not found")
        return {"ok": True, "id": annotation_id}

    @app.post("/api/gsc/sync")
    def sync_gsc(payload: SourceSyncRequest = SourceSyncRequest()) -> dict[str, Any]:
        return analytics.run_gsc_sync(payload.force)

    @app.post("/api/ga4/sync")
    def sync_ga4(payload: SourceSyncRequest = SourceSyncRequest()) -> dict[str, Any]:
        return analytics.run_ga4_sync(payload.force)

    @app.post("/api/pagespeed/sync")
    def sync_pagespeed(payload: PageSpeedSyncRequest) -> dict[str, Any]:
        try:
            return pagespeed_service.analyze(payload.url, [payload.strategy])
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    @app.post("/api/pagespeed/analyze")
    def analyze_pagespeed(payload: PageSpeedAnalyzeRequest) -> dict[str, Any]:
        try:
            return pagespeed_service.analyze(payload.url, payload.strategies, payload.categories, payload.locale)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    @app.post("/api/crux/sync")
    def sync_crux() -> dict[str, Any]:
        return analytics.run_crux_sync()

    @app.post("/api/system/shutdown")
    def shutdown() -> dict[str, Any]:
        threading.Timer(0.2, lambda: os._exit(0)).start()
        return {"ok": True, "message": "Shutdown scheduled."}

    web_dist = Path(__file__).resolve().parents[1] / "web" / "dist"
    if web_dist.exists():
        mimetypes.add_type("image/webp", ".webp")
        app.mount("/", StaticFiles(directory=web_dist, html=True), name="web")

    return app


app = create_app()
