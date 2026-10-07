\echo '=== Reset tables ==='
TRUNCATE telemetry_history, drone_latest_state;

\echo '=== Experiment A: same event twice (with ON CONFLICT) ==='
INSERT INTO telemetry_history (event_id, drone_id, occurred_at, latitude, longitude,
  altitude_m, speed_mps, battery_pct, gps_satellites, heading_deg, status)
VALUES ('11111111-1111-1111-1111-111111111111', 'SF-PN-001', '2026-10-07T10:00:00Z',
  18.52, 73.85, 80, 10, 90, 14, 0, 'FLYING')
ON CONFLICT (event_id) DO NOTHING;

INSERT INTO telemetry_history (event_id, drone_id, occurred_at, latitude, longitude,
  altitude_m, speed_mps, battery_pct, gps_satellites, heading_deg, status)
VALUES ('11111111-1111-1111-1111-111111111111', 'SF-PN-001', '2026-10-07T10:00:00Z',
  18.52, 73.85, 80, 10, 90, 14, 0, 'FLYING')
ON CONFLICT (event_id) DO NOTHING;

\echo '--- same event again WITHOUT ON CONFLICT (expect an error) ---'
INSERT INTO telemetry_history (event_id, drone_id, occurred_at, latitude, longitude,
  altitude_m, speed_mps, battery_pct, gps_satellites, heading_deg, status)
VALUES ('11111111-1111-1111-1111-111111111111', 'SF-PN-001', '2026-10-07T10:00:00Z',
  18.52, 73.85, 80, 10, 90, 14, 0, 'FLYING');

\echo '=== Experiment B: latest state only moves forward ==='
PREPARE upsert_state(uuid, timestamptz, smallint) AS
INSERT INTO drone_latest_state (drone_id, event_id, occurred_at, latitude, longitude,
  altitude_m, speed_mps, battery_pct, gps_satellites, heading_deg, status)
VALUES ('SF-PN-001', $1, $2, 18.53, 73.85, 80, 10, $3, 14, 0, 'FLYING')
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
WHERE EXCLUDED.occurred_at > drone_latest_state.occurred_at;

\echo '--- step 1: first message, 10:00:05, battery 89 ---'
EXECUTE upsert_state('22222222-2222-2222-2222-222222222222', '2026-10-07T10:00:05Z', 89);

\echo '--- step 2: LATE message, 10:00:02, battery 91 ---'
EXECUTE upsert_state('33333333-3333-3333-3333-333333333333', '2026-10-07T10:00:02Z', 91);

\echo '--- step 3: state after the late message (expect 89) ---'
SELECT drone_id, occurred_at, battery_pct FROM drone_latest_state;

\echo '--- step 4: NEWER message, 10:00:08, battery 88 ---'
EXECUTE upsert_state('44444444-4444-4444-4444-444444444444', '2026-10-07T10:00:08Z', 88);
SELECT drone_id, occurred_at, battery_pct FROM drone_latest_state;