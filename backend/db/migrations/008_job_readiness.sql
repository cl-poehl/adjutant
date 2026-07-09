-- 008: per-role readiness plan (the concrete step to become a fit / unblock).

BEGIN;

ALTER TABLE jobs ADD COLUMN IF NOT EXISTS readiness TEXT NOT NULL DEFAULT '';

COMMIT;
