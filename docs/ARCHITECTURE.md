# Architecture

SEO Data Console uses a local-first architecture with an optional cloud replica.

## Current Choice

Use this stack for the current phase:

- Frontend: React, TypeScript, and Vite under `apps/web/`.
- Backend: FastAPI under `apps/api/`, serving the production frontend build and structured API endpoints.
- Local data source of truth: raw API exports plus SQLite operational tables.
- Cloud database: Supabase Postgres as a replica and analysis database.
- Sync safety: create local backups before every cloud upload.
- Frozen reference: `apps/seo_dashboard/` is not an active development or runtime dependency.

## Why This Architecture

The project handles private analytics data and API credentials. Keeping raw exports and SQLite local by default reduces risk while the dashboard data model is still evolving.

Supabase Postgres is useful as a shared analysis layer for multiple tools, but it should not replace local raw files until backup, retention, and stability policies are final.

## Data Flow

```text
Google APIs
  -> tools/*.py connector CLIs
  -> data/*/raw/ audit exports
  -> data/local/seo_dashboard.sqlite operational and normalized facts
  -> apps/api/ FastAPI services and endpoints
  -> apps/web/ React analysis workflows

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
- Organize GSC, GA4, Page Experience, AI tasks, operations, and connections by human SEO task.
- Treat Supabase as cloud replica status, not as the only data source.

## Database Responsibilities

SQLite should hold local operational state:

- API run history.
- Latest PageSpeed result and latest-attempt evidence keyed by normalized URL/device.
- GSC/GA4 normalized facts, saved analysis state, annotations, and AI task metadata.

Supabase should hold replicated analysis tables:

- Raw file metadata.
- GSC rows.
- GA4 rows.
- Latest PageSpeed URL/device results using equivalent unique upsert semantics.
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

## Active And Frozen Applications

`apps/api/` and `apps/web/` are the sole active application development path and are independently runnable. The dependency-free dashboard under `apps/seo_dashboard/` remains a frozen behavioral reference and temporary fallback. It may be removed only after the parity, data, operations, browser, rollback, and explicit-approval gates in `.ai/FRONTEND_BACKEND_MIGRATION_GATE.md` pass; routine fixes and new features do not belong there.

## PageSpeed Retention

PageSpeed active identity is `(normalized_requested_url, strategy)`. SQLite, deterministic raw files, and optional Supabase replication keep only the latest validated successful Mobile or Desktop result for that key. A failed attempt may update lightweight status evidence but never replaces the previous success or stores historical scores, audits, or raw payloads as active history.
