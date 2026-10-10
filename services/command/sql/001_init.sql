CREATE TABLE IF NOT EXISTS commands (
    command_id       UUID PRIMARY KEY,
    idempotency_key  TEXT UNIQUE,
    drone_id         TEXT NOT NULL,
    site_id          TEXT NOT NULL,
    type             TEXT NOT NULL,
    target_lat       DOUBLE PRECISION,
    target_lon       DOUBLE PRECISION,
    state            TEXT NOT NULL,
    attempts         INT NOT NULL DEFAULT 0,
    next_attempt_at  TIMESTAMPTZ,
    expires_at       TIMESTAMPTZ NOT NULL,
    reason           TEXT,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_commands_retry
    ON commands (state, next_attempt_at);