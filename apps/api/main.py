from __future__ import annotations

import datetime as dt
from typing import Any

from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from apps.api.core.config import masked_env, settings
from apps.api.services import legacy_bridge, storage_service


class PageSpeedSyncRequest(BaseModel):
    url: str = ""
    strategy: str = "mobile"


def create_app() -> FastAPI:
    cfg = settings()
    app = FastAPI(title=cfg.app_name, version="0.2.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://127.0.0.1:5173", "http://localhost:5173", "http://127.0.0.1:8766"],
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
        return {"env": masked_env(), **legacy_bridge.status()}

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
        limit: int = Query(default=50, ge=1, le=200),
    ) -> dict[str, Any]:
        return legacy_bridge.gsc_explorer(
            {
                "query": [query],
                "page": [page],
                "start": [start],
                "end": [end],
                "minImpressions": [str(minImpressions)],
                "sort": [sort],
                "limit": [str(limit)],
            }
        )

    @app.get("/api/ga4/analytics")
    def ga4_analytics(channel: str = "") -> dict[str, Any]:
        return legacy_bridge.ga4_analytics({"channel": [channel]})

    @app.get("/api/pagespeed/history")
    def pagespeed_history(url: str = "", strategy: str = "") -> dict[str, Any]:
        return legacy_bridge.pagespeed_history({"url": [url], "strategy": [strategy]})

    @app.get("/api/crux/summary")
    def crux_summary() -> dict[str, Any]:
        return legacy_bridge.crux_summary()

    @app.post("/api/gsc/sync")
    def sync_gsc() -> dict[str, Any]:
        return legacy_bridge.sync_gsc()

    @app.post("/api/ga4/sync")
    def sync_ga4() -> dict[str, Any]:
        return legacy_bridge.sync_ga4()

    @app.post("/api/pagespeed/sync")
    def sync_pagespeed(payload: PageSpeedSyncRequest) -> dict[str, Any]:
        return legacy_bridge.sync_pagespeed(payload.url, payload.strategy)

    @app.post("/api/crux/sync")
    def sync_crux() -> dict[str, Any]:
        return legacy_bridge.sync_crux()

    return app


app = create_app()
