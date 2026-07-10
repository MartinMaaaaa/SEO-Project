CREATE TABLE IF NOT EXISTS seo_raw_files (
    file_sha256 TEXT PRIMARY KEY,
    source TEXT NOT NULL,
    relative_path TEXT NOT NULL,
    file_name TEXT NOT NULL,
    extension TEXT NOT NULL,
    bytes BIGINT NOT NULL,
    modified_at TIMESTAMPTZ,
    backed_up_path TEXT,
    payload JSONB,
    uploaded_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_seo_raw_files_source_uploaded
    ON seo_raw_files (source, uploaded_at DESC);

CREATE TABLE IF NOT EXISTS gsc_performance_rows (
    file_sha256 TEXT NOT NULL REFERENCES seo_raw_files(file_sha256) ON DELETE CASCADE,
    row_index INTEGER NOT NULL,
    site_property TEXT,
    start_date DATE,
    end_date DATE,
    dimensions TEXT[],
    date DATE,
    query TEXT,
    page TEXT,
    clicks DOUBLE PRECISION NOT NULL DEFAULT 0,
    impressions DOUBLE PRECISION NOT NULL DEFAULT 0,
    ctr DOUBLE PRECISION NOT NULL DEFAULT 0,
    position DOUBLE PRECISION NOT NULL DEFAULT 0,
    raw_row JSONB NOT NULL,
    uploaded_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (file_sha256, row_index)
);

CREATE INDEX IF NOT EXISTS idx_gsc_performance_date
    ON gsc_performance_rows (date);

CREATE INDEX IF NOT EXISTS idx_gsc_performance_query
    ON gsc_performance_rows (query);

CREATE INDEX IF NOT EXISTS idx_gsc_performance_page
    ON gsc_performance_rows (page);

CREATE TABLE IF NOT EXISTS ga4_report_rows (
    file_sha256 TEXT NOT NULL REFERENCES seo_raw_files(file_sha256) ON DELETE CASCADE,
    row_index INTEGER NOT NULL,
    property_id TEXT,
    start_date DATE,
    end_date DATE,
    date DATE,
    session_default_channel_group TEXT,
    sessions DOUBLE PRECISION NOT NULL DEFAULT 0,
    total_users DOUBLE PRECISION NOT NULL DEFAULT 0,
    active_users DOUBLE PRECISION NOT NULL DEFAULT 0,
    screen_page_views DOUBLE PRECISION NOT NULL DEFAULT 0,
    engaged_sessions DOUBLE PRECISION NOT NULL DEFAULT 0,
    raw_row JSONB NOT NULL,
    uploaded_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (file_sha256, row_index)
);

CREATE INDEX IF NOT EXISTS idx_ga4_report_date
    ON ga4_report_rows (date);

CREATE INDEX IF NOT EXISTS idx_ga4_report_channel
    ON ga4_report_rows (session_default_channel_group);

CREATE TABLE IF NOT EXISTS pagespeed_report_runs (
    file_sha256 TEXT PRIMARY KEY REFERENCES seo_raw_files(file_sha256) ON DELETE CASCADE,
    requested_url TEXT,
    final_url TEXT,
    strategy TEXT,
    fetched_at TIMESTAMPTZ,
    performance DOUBLE PRECISION,
    accessibility DOUBLE PRECISION,
    best_practices DOUBLE PRECISION,
    seo DOUBLE PRECISION,
    lcp TEXT,
    tbt TEXT,
    cls TEXT,
    speed_index TEXT,
    summary JSONB NOT NULL,
    uploaded_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_pagespeed_report_url_time
    ON pagespeed_report_runs (requested_url, fetched_at DESC);

CREATE TABLE IF NOT EXISTS crux_report_runs (
    file_sha256 TEXT PRIMARY KEY REFERENCES seo_raw_files(file_sha256) ON DELETE CASCADE,
    target_type TEXT,
    target TEXT,
    form_factor TEXT,
    collection_period JSONB,
    summary JSONB NOT NULL,
    uploaded_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS seo_api_runs (
    local_id INTEGER NOT NULL,
    source TEXT NOT NULL,
    status TEXT NOT NULL,
    command TEXT,
    summary JSONB,
    raw_path TEXT,
    error TEXT,
    created_at TIMESTAMPTZ,
    uploaded_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (source, local_id)
);

CREATE INDEX IF NOT EXISTS idx_seo_api_runs_source_created
    ON seo_api_runs (source, created_at DESC);

CREATE TABLE IF NOT EXISTS local_backup_manifests (
    backup_id TEXT PRIMARY KEY,
    label TEXT NOT NULL,
    backup_path TEXT NOT NULL,
    manifest JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
