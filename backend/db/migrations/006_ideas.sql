-- 006: daily startup-idea engine.

BEGIN;

CREATE TABLE IF NOT EXISTS ideas (
    id           SERIAL PRIMARY KEY,
    created_date TEXT NOT NULL,            -- YYYY-MM-DD the idea was generated
    title        TEXT NOT NULL,
    pitch        TEXT NOT NULL DEFAULT '',
    domain       TEXT NOT NULL DEFAULT '',
    score        INTEGER NOT NULL DEFAULT 3,   -- 1–5: fit × timing × buildability
    why_now      TEXT NOT NULL DEFAULT '',
    why_you      TEXT NOT NULL DEFAULT '',
    first_step   TEXT NOT NULL DEFAULT '',
    market       TEXT NOT NULL DEFAULT '',
    signal       TEXT NOT NULL DEFAULT '',     -- the trend/news it rides (+ source)
    status       TEXT NOT NULL DEFAULT 'new'   -- new | saved | dismissed
        CONSTRAINT ck_idea_status CHECK (status IN ('new','saved','dismissed')),
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_ideas_status ON ideas (status);
CREATE INDEX IF NOT EXISTS idx_ideas_date   ON ideas (created_date);

COMMIT;
