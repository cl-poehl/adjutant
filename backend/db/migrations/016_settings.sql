-- 016: runtime key/value settings — backs the dashboard automation toggles
-- (ideas / jobs / research brief) so the paid daily jobs can be turned on and
-- off live without redeploying or editing env vars.

BEGIN;

CREATE TABLE IF NOT EXISTS settings (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL DEFAULT ''
);

COMMIT;
