-- 007: job scout.

BEGIN;

CREATE TABLE IF NOT EXISTS jobs (
    id            SERIAL PRIMARY KEY,
    found_date    TEXT NOT NULL,              -- YYYY-MM-DD scouted
    title         TEXT NOT NULL,
    company       TEXT NOT NULL DEFAULT '',
    location      TEXT NOT NULL DEFAULT '',
    comp          TEXT NOT NULL DEFAULT '',   -- salary / comp estimate
    url           TEXT NOT NULL DEFAULT '',
    fit_score     INTEGER NOT NULL DEFAULT 3, -- 1–5 profile fit
    trajectory    INTEGER NOT NULL DEFAULT 3, -- 1–5 career-evolution value
    why_fit       TEXT NOT NULL DEFAULT '',   -- why his profile matches
    why_step_up   TEXT NOT NULL DEFAULT '',   -- why it's a strong career move
    watch_outs    TEXT NOT NULL DEFAULT '',   -- risks / gaps to close
    source        TEXT NOT NULL DEFAULT '',
    status        TEXT NOT NULL DEFAULT 'new' -- new | saved | dismissed
        CONSTRAINT ck_job_status CHECK (status IN ('new','saved','dismissed')),
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs (status);

COMMIT;
