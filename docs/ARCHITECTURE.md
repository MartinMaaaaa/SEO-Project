# Architecture

SEO Data Console uses a local-first architecture with an optional cloud replica.

## Current Choice

Use this stack for the current phase:

- Frontend: static HTML, CSS, and JavaScript served by the local dashboard.
- Backend: Python standard-library HTTP server as a local API facade.
- Local data source of truth: raw API exports plus SQLite operational tables.
- Cloud database: Supabase Postgres as a replica and analysis database.
- Sync safety: create local backups before every cloud upload.

## Why This Architecture

The project handles private analytics data and API credentials. Keeping raw exports and SQLite local by default reduces risk while the dashboard data model is still evolving.

Supabase Postgres is useful as a shared analysis layer for multiple tools, but it should not replace local raw files until backup, retention, and stability policies are final.

## Data Flow

```text
Google APIs
  -> tools/*.py connector CLIs
  -> data/*/raw/ audit exports
  -> data/local/seo_dashboard.sqlite operational status
  -> apps/seo_dashboard/server.py API endpoints
  -> apps/seo_dashboard/static/ browser UI

Optional cloud path:

data/*/raw/ + SQLite
  -> local backup manifest
  -> Supabase Postgres tables
  -> dashboard storage and upload status
```

## Backend Responsibilities

The backend should:

- Trigger controlled sync commands.
- Redact API errors before returning them to the UI.
- Read local raw exports and SQLite summaries.
- Expose structured endpoints rather than making the frontend parse files.
- Upload successful exports to Supabase only when configured.

## Frontend Responsibilities

The frontend should:

- Render analysis workflows, not raw files.
- Show freshness, quota, and sync health before encouraging refreshes.
- Keep GSC, GA4, PageSpeed, CrUX, AI tasks, storage, and settings as separate views.
- Treat Supabase as cloud replica status, not as the only data source.

## Database Responsibilities

SQLite should hold local operational state:

- API run history.
- PageSpeed run history.
- Future local fact tables and AI task metadata.

Supabase should hold replicated analysis tables:

- Raw file metadata.
- GSC rows.
- GA4 rows.
- PageSpeed runs.
- CrUX runs.
- API run history.
- Backup manifests.

## Migration Rule

Do not move to cloud-primary storage until all of these are true:

- The dashboard can show database status and upload history.
- Local backups are verified after sync.
- Duplicate uploads are idempotent.
- Retention rules are documented.
- The user explicitly approves cloud-primary storage.

## Modern Web App Migration

`apps/api/` and `apps/web/` are now the sole active application development path. They must preserve the local-first storage contract while migrating proven connector and dashboard behavior. The dependency-free dashboard under `apps/seo_dashboard/` is frozen as a behavioral reference and temporary fallback. It may be removed only after the parity, data, operations, browser, rollback, and explicit-approval gates in `.ai/FRONTEND_BACKEND_MIGRATION_GATE.md` pass.
