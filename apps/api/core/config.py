from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
ENV_PATH = ROOT / ".env"


@dataclass(frozen=True)
class Settings:
    app_name: str = "SEO Data Console API"
    environment: str = "local"
    database_mode: str = "local_first_cloud_replica"
    cloud_provider: str = "supabase"
    local_backup_policy: str = "raw_exports_sqlite_and_backup_manifests"
    api_prefix: str = "/api"


def load_env() -> dict[str, str]:
    values: dict[str, str] = {}
    if ENV_PATH.exists():
        for raw_line in ENV_PATH.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            values[key.strip()] = value.strip().strip('"').strip("'")
    for key, value in os.environ.items():
        if key.startswith(("GSC_", "GA4_", "PAGESPEED_", "CRUX_", "SUPABASE_", "SITE_", "TARGET_", "BRAND_", "PRIMARY_")):
            values[key] = value
    return values


def mask_secret(value: str) -> str:
    if not value:
        return ""
    if len(value) <= 8:
        return "***"
    return f"{value[:4]}...{value[-4:]}"


def masked_env() -> dict[str, dict[str, object]]:
    env = load_env()
    keys = [
        "GSC_SITE_URL",
        "GSC_OAUTH_CLIENT_ID",
        "GSC_OAUTH_CLIENT_SECRET",
        "GSC_OAUTH_REFRESH_TOKEN",
        "GA4_PROPERTY_ID",
        "GA4_OAUTH_CLIENT_ID",
        "GA4_OAUTH_CLIENT_SECRET",
        "GA4_OAUTH_REFRESH_TOKEN",
        "PAGESPEED_API_KEY",
        "CRUX_API_KEY",
        "SUPABASE_URL",
        "SUPABASE_POOLER_URL",
        "SUPABASE_DATABASE_URL",
        "SUPABASE_ANON_KEY",
        "SUPABASE_SERVICE_ROLE_KEY",
    ]
    result: dict[str, dict[str, object]] = {}
    for key in keys:
        value = env.get(key, "")
        secret = any(token in key for token in ("SECRET", "TOKEN", "KEY", "URL"))
        result[key] = {"configured": bool(value), "value": mask_secret(value) if secret else value}
    return result


def settings() -> Settings:
    return Settings()
