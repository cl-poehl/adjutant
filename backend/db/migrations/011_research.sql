-- 011: research agent — standing topics the agent digs into + their findings.

BEGIN;

CREATE TABLE IF NOT EXISTS research_topics (
    id           SERIAL PRIMARY KEY,
    query        TEXT NOT NULL,
    cadence      TEXT NOT NULL DEFAULT 'once' CHECK (cadence IN ('once','daily')),
    status       TEXT NOT NULL DEFAULT 'queued'
                 CHECK (status IN ('queued','running','done','error')),
    last_summary TEXT NOT NULL DEFAULT '',
    last_error   TEXT NOT NULL DEFAULT '',
    last_run_at  TIMESTAMPTZ,
    archived     BOOLEAN NOT NULL DEFAULT FALSE,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS research_findings (
    id          SERIAL PRIMARY KEY,
    topic_id    INTEGER NOT NULL REFERENCES research_topics(id) ON DELETE CASCADE,
    run_date    TEXT NOT NULL,
    title       TEXT NOT NULL,
    detail      TEXT NOT NULL DEFAULT '',
    why_matters TEXT NOT NULL DEFAULT '',
    url         TEXT NOT NULL DEFAULT '',
    source      TEXT NOT NULL DEFAULT '',
    importance  INTEGER NOT NULL DEFAULT 3,
    status      TEXT NOT NULL DEFAULT 'new'
                CHECK (status IN ('new','saved','dismissed')),
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS ix_findings_topic ON research_findings (topic_id);

COMMIT;
