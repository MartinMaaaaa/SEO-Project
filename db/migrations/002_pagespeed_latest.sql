CREATE TABLE IF NOT EXISTS pagespeed_latest_results (
    active_key TEXT PRIMARY KEY,
    url_key TEXT NOT NULL,
    requested_url TEXT NOT NULL,
    final_url TEXT,
    strategy TEXT NOT NULL CHECK (strategy IN ('mobile', 'desktop')),
    fetched_at TIMESTAMPTZ,
    saved_at TIMESTAMPTZ NOT NULL,
    lighthouse_version TEXT,
    locale TEXT,
    raw_reference TEXT,
    result JSONB NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (url_key, strategy)
);

CREATE INDEX IF NOT EXISTS idx_pagespeed_latest_saved
    ON pagespeed_latest_results (saved_at DESC);
