-- 005: tick-off-as-completed for agenda items.

BEGIN;

ALTER TABLE emails ADD COLUMN IF NOT EXISTS done BOOLEAN NOT NULL DEFAULT FALSE;

COMMIT;
