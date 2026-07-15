# SEO Data Console API

FastAPI backend for the professional web app architecture.

## Role

- Source of truth: local raw API exports and SQLite.
- Cloud replica: Supabase Postgres.
- Local backup: versioned upload snapshots and backup manifests.
- Runtime independence: native services read local caches/SQLite and call connector CLIs without importing the frozen application.

## Run Locally

```powershell
python -m uvicorn apps.api.main:app --host 127.0.0.1 --port 8787
```

Open:

```text
http://127.0.0.1:8787/api/health
```

The root English/Chinese launchers start React/Vite at `http://127.0.0.1:5173/` and FastAPI at `http://127.0.0.1:8787/` as separate processes. Vite proxies `/api` requests to FastAPI.

## Notes

The API reads `.env` without modifying it. It masks secrets in status responses and keeps existing Google API and Supabase variables unchanged.
