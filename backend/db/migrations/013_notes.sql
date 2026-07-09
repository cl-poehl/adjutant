-- 013: second brain — notes & bookmarks the user can query over.

BEGIN;

CREATE TABLE IF NOT EXISTS notes (
    id         SERIAL PRIMARY KEY,
    kind       TEXT NOT NULL DEFAULT 'note' CHECK (kind IN ('note','bookmark')),
    title      TEXT NOT NULL DEFAULT '',
    content    TEXT NOT NULL DEFAULT '',
    url        TEXT NOT NULL DEFAULT '',
    tags       TEXT NOT NULL DEFAULT '',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

COMMIT;
