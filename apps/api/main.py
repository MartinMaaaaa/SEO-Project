from __future__ import annotations

import datetime as dt
import os
from pathlib import Path
import threading
from typing import Any

from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from apps.api.core.config import masked_env, settings
from apps.api.services import analytics, storage_service


class PageSpeedSyncRequest(BaseModel):
    url: str = ""
    strategy: str = "mobile"


class AiTaskRequest(BaseModel):
    taskType: str = "seo_analysis"
    title: str = "Scoped SEO analysis"
    scope: dict[str, Any] = {}
    evidence: dict[str, Any] = {}


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

    @app.get("/api/ga4/analytics")
    def ga4_analytics(channel: str = "") -> dict[str, Any]:
        return analytics.ga4_analytics({"channel": [channel]})

    @app.get("/api/pagespeed/history")
    def pagespeed_history(url: str = "", strategy: str = "") -> dict[str, Any]:
        return analytics.pagespeed_history({"url": [url], "strategy": [strategy]})

    @app.get("/api/crux/summary")
    def crux_summary() -> dict[str, Any]:
        return analytics.summarize_crux()

    @app.get("/api/ai/tasks")
    def ai_tasks(limit: int = Query(default=30, ge=1, le=100)) -> list[dict[str, Any]]:
        return analytics.recent_ai_tasks(limit)

    @app.post("/api/ai/tasks")
    def create_ai_task(payload: AiTaskRequest) -> dict[str, Any]:
        return analytics.generate_ai_task(payload.model_dump())

    @app.post("/api/gsc/sync")
    def sync_gsc() -> dict[str, Any]:
        return analytics.run_gsc_sync()

    @app.post("/api/ga4/sync")
    def sync_ga4() -> dict[str, Any]:
        return analytics.run_ga4_sync()

    @app.post("/api/pagespeed/sync")
    def sync_pagespeed(payload: PageSpeedSyncRequest) -> dict[str, Any]:
        return analytics.run_pagespeed_sync(payload.url, payload.strategy)

    @app.post("/api/crux/sync")
    def sync_crux() -> dict[str, Any]:
        return analytics.run_crux_sync()

    @app.post("/api/system/shutdown")
    def shutdown() -> dict[str, Any]:
        threading.Timer(0.2, lambda: os._exit(0)).start()
        return {"ok": True, "message": "Shutdown scheduled."}

    web_dist = Path(__file__).resolve().parents[1] / "web" / "dist"
    if web_dist.exists():
        app.mount("/", StaticFiles(directory=web_dist, html=True), name="web")

    return app


app = create_app()
