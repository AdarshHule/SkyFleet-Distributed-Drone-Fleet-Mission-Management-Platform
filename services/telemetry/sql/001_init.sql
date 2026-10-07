CREATE TABLE IF NOT EXISTS telemetry_history (
    event_id        UUID PRIMARY KEY,
    drone_id        TEXT NOT NULL,
    occurred_at     TIMESTAMPTZ NOT NULL,
    received_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    latitude        DOUBLE PRECISION NOT NULL,
    longitude       DOUBLE PRECISION NOT NULL,
    altitude_m      DOUBLE PRECISION NOT NULL,
    speed_mps       DOUBLE PRECISION NOT NULL,
    battery_pct     SMALLINT NOT NULL,
    gps_satellites  SMALLINT NOT NULL,
    heading_deg     DOUBLE PRECISION NOT NULL,
    status          TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_history_drone_time
    ON telemetry_history (drone_id, occurred_at DESC);

CREATE TABLE IF NOT EXISTS drone_latest_state (
    drone_id        TEXT PRIMARY KEY,
    event_id        UUID NOT NULL,
    occurred_at     TIMESTAMPTZ NOT NULL,
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    latitude        DOUBLE PRECISION NOT NULL,
    longitude       DOUBLE PRECISION NOT NULL,
    altitude_m      DOUBLE PRECISION NOT NULL,
    speed_mps       DOUBLE PRECISION NOT NULL,
    battery_pct     SMALLINT NOT NULL,
    gps_satellites  SMALLINT NOT NULL,
    heading_deg     DOUBLE PRECISION NOT NULL,
    status          TEXT NOT NULL
);
