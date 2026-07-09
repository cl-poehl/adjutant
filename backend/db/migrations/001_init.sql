-- Adjutant v1 — initial schema (Postgres).
-- Mirrors backend/db/models.py exactly. Run with:
--   psql "$DATABASE_URL" -f backend/db/migrations/001_init.sql

BEGIN;

CREATE TABLE IF NOT EXISTS projects (
    id          SERIAL PRIMARY KEY,
    name        TEXT NOT NULL UNIQUE,
    -- Doubles as classification context: describe what belongs in the project.
    description TEXT NOT NULL DEFAULT '',
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- One row per thread, normalized and provider-agnostic.
-- `provider` keeps Gmail and (later) Outlook rows coexisting in one table.
CREATE TABLE IF NOT EXISTS emails (
    id                 SERIAL PRIMARY KEY,
    provider           TEXT NOT NULL DEFAULT 'gmail',
    provider_thread_id TEXT NOT NULL,
    project_id         INTEGER REFERENCES projects(id) ON DELETE SET NULL,
    subject            TEXT NOT NULL DEFAULT '',
    last_sender        TEXT NOT NULL DEFAULT '',
    snippet            TEXT NOT NULL DEFAULT '',
    status             TEXT NOT NULL DEFAULT 'new'
        CONSTRAINT ck_email_status CHECK
        (status IN ('new','classified','needs_reply','drafted','sent','ignored')),
    draft_id           TEXT,
    draft_body         TEXT,
    processed          BOOLEAN NOT NULL DEFAULT FALSE,  -- idempotency flag
    updated_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_provider_thread UNIQUE (provider, provider_thread_id)
);

CREATE INDEX IF NOT EXISTS idx_emails_project ON emails (project_id);
CREATE INDEX IF NOT EXISTS idx_emails_status  ON emails (status);

-- Later phases (do NOT create now — documented so this schema isn't boxed in):
--   meetings(id, project_id FK, ...), action_items(id, project_id FK, ...),
--   projects.progress / projects.next_step columns.

COMMIT;
