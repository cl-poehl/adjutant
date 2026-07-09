-- 003: digest categories.
-- Low-priority feed buckets (newsletters etc.) live in a muted "Digest"
-- section and are summarized by an AI briefing instead of being read.

BEGIN;

ALTER TABLE projects ADD COLUMN IF NOT EXISTS digest BOOLEAN NOT NULL DEFAULT FALSE;

COMMIT;
