import psycopg

from skyfleet_contracts import Envelope, TelemetryV1

INSERT_HISTORY = """
INSERT INTO telemetry_history (event_id, drone_id, occurred_at, latitude, longitude,
  altitude_m, speed_mps, battery_pct, gps_satellites, heading_deg, status)
VALUES (%(event_id)s, %(drone_id)s, %(occurred_at)s, %(latitude)s, %(longitude)s,
  %(altitude_m)s, %(speed_mps)s, %(battery_pct)s, %(gps_satellites)s, %(heading_deg)s,
  %(status)s)
ON CONFLICT (event_id) DO NOTHING
"""

UPSERT_LATEST = """
INSERT INTO drone_latest_state (drone_id, event_id, occurred_at, latitude, longitude,
  altitude_m, speed_mps, battery_pct, gps_satellites, heading_deg, status)
VALUES (%(drone_id)s, %(event_id)s, %(occurred_at)s, %(latitude)s, %(longitude)s,
  %(altitude_m)s, %(speed_mps)s, %(battery_pct)s, %(gps_satellites)s, %(heading_deg)s,
  %(status)s)
ON CONFLICT (drone_id) DO UPDATE SET
  event_id = EXCLUDED.event_id,
  occurred_at = EXCLUDED.occurred_at,
  latitude = EXCLUDED.latitude,
  longitude = EXCLUDED.longitude,
  altitude_m = EXCLUDED.altitude_m,
  speed_mps = EXCLUDED.speed_mps,
  battery_pct = EXCLUDED.battery_pct,
  gps_satellites = EXCLUDED.gps_satellites,
  heading_deg = EXCLUDED.heading_deg,
  status = EXCLUDED.status,
  updated_at = now()
WHERE EXCLUDED.occurred_at > drone_latest_state.occurred_at
"""


def connect(url: str) -> psycopg.Connection:
    return psycopg.connect(url, autocommit=True)


def to_row(env: Envelope[TelemetryV1]) -> dict:
    """Flatten an envelope into the named parameters used by the SQL above."""
    p = env.payload
    return {
        "event_id": env.event_id,
        "occurred_at": env.occurred_at,
        "drone_id": p.drone_id,
        "latitude": p.latitude,
        "longitude": p.longitude,
        "altitude_m": p.altitude_m,
        "speed_mps": p.speed_mps,
        "battery_pct": p.battery_pct,
        "gps_satellites": p.gps_satellites,
        "heading_deg": p.heading_deg,
        "status": p.status.value,
    }


class TelemetryStore:
    def __init__(self, conn: psycopg.Connection) -> None:
        self.conn = conn

    def save(self, env: Envelope[TelemetryV1]) -> tuple[bool, bool]:
        """Store one telemetry message.

        Returns (history_inserted, latest_updated).
        """
        row = to_row(env)

        with self.conn.transaction():
            history_cur = self.conn.execute(INSERT_HISTORY, row)
            history_inserted = history_cur.rowcount == 1

            latest_cur = self.conn.execute(UPSERT_LATEST, row)
            latest_updated = latest_cur.rowcount == 1

        return history_inserted, latest_updated
