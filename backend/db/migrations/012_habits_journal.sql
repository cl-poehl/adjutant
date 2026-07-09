-- 012: habits + journal — personal command-deck tracking.

BEGIN;

CREATE TABLE IF NOT EXISTS habits (
    id         SERIAL PRIMARY KEY,
    name       TEXT NOT NULL,
    emoji      TEXT NOT NULL DEFAULT '',
    sort       INTEGER NOT NULL DEFAULT 0,
    archived   BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS habit_logs (
    id       SERIAL PRIMARY KEY,
    habit_id INTEGER NOT NULL REFERENCES habits(id) ON DELETE CASCADE,
    day      TEXT NOT NULL,
    UNIQUE (habit_id, day)
);

CREATE TABLE IF NOT EXISTS journal_entries (
    id         SERIAL PRIMARY KEY,
    day        TEXT NOT NULL UNIQUE,
    text       TEXT NOT NULL DEFAULT '',
    mood       TEXT NOT NULL DEFAULT '',
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

COMMIT;
