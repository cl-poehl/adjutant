-- 015: detect new messages on already-processed threads, so a stale draft is
-- replaced instead of silently kept. Stores the last triaged message id.

BEGIN;

ALTER TABLE emails ADD COLUMN IF NOT EXISTS last_seen_message_id TEXT;

COMMIT;
