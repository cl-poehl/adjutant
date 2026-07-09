-- 014: daily research brief — a 'track' on topics + a synthesized daily brief.

BEGIN;

ALTER TABLE research_topics
    ADD COLUMN IF NOT EXISTS track TEXT NOT NULL DEFAULT 'you'
    CHECK (track IN ('you','venture'));

CREATE TABLE IF NOT EXISTS research_briefs (
    id         SERIAL PRIMARY KEY,
    day        TEXT NOT NULL UNIQUE,
    for_you    TEXT NOT NULL DEFAULT '',
    ventures   TEXT NOT NULL DEFAULT '',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

COMMIT;
