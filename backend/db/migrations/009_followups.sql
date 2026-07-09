-- 009: follow-up radar — track threads where I'm waiting on a reply.

BEGIN;

ALTER TABLE emails ADD COLUMN IF NOT EXISTS awaiting_since TIMESTAMPTZ;

COMMIT;
