-- 004: urgency scoring at classify-time + agenda snooze.

BEGIN;

-- 'high' | 'normal' — scored by the classifier in the same call (free).
ALTER TABLE emails ADD COLUMN IF NOT EXISTS urgency TEXT;
-- Threads snoozed off the agenda until this moment.
ALTER TABLE emails ADD COLUMN IF NOT EXISTS snoozed_until TIMESTAMPTZ;

COMMIT;
