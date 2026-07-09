-- 010: events scout — real-world events in the selected city matched to interests.

BEGIN;

CREATE TABLE IF NOT EXISTS events (
    id          SERIAL PRIMARY KEY,
    found_date  TEXT NOT NULL,
    city        TEXT NOT NULL DEFAULT '',
    title       TEXT NOT NULL,
    category    TEXT NOT NULL DEFAULT '',
    venue       TEXT NOT NULL DEFAULT '',
    "when"      TEXT NOT NULL DEFAULT '',
    deadline    TEXT NOT NULL DEFAULT '',
    price       TEXT NOT NULL DEFAULT '',
    url         TEXT NOT NULL DEFAULT '',
    fit_score   INTEGER NOT NULL DEFAULT 3,
    why_fit     TEXT NOT NULL DEFAULT '',
    description TEXT NOT NULL DEFAULT '',
    source      TEXT NOT NULL DEFAULT '',
    status      TEXT NOT NULL DEFAULT 'new'
                CHECK (status IN ('new','saved','dismissed')),
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS ix_events_status ON events (status);

COMMIT;
