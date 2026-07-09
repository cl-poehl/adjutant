-- 002: auto-organize support.
-- Adds a flag distinguishing user-created projects from categories that the
-- auto-organize pass discovered from the mail itself.

BEGIN;

ALTER TABLE projects ADD COLUMN IF NOT EXISTS auto BOOLEAN NOT NULL DEFAULT FALSE;

COMMIT;
