import os
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import psycopg
import pytest

from skyfleet_contracts import Envelope, TelemetryV1
from skyfleet_telemetry.store import TelemetryStore

TEST_DB_URL = os.getenv(
    "TEST_DATABASE_URL",
    "postgresql://skyfleet:change-me-local-only@localhost:5432/skyfleet_test",
)
T0 = datetime(2026, 10, 7, 10, 0, tzinfo=timezone.utc)


@pytest.fixture
def store():
    with psycopg.connect(TEST_DB_URL, autocommit=True) as conn:
        conn.execute("TRUNCATE telemetry_history, drone_latest_state")
        yield TelemetryStore(conn)


def make_env(seconds: int, battery: int) -> Envelope[TelemetryV1]:
    return Envelope[TelemetryV1](
        event_type="drone.telemetry",
        producer="test",
        occurred_at=T0 + timedelta(seconds=seconds),
        payload=TelemetryV1(
            drone_id="SF-PN-001",
            latitude=18.52,
            longitude=73.85,
            altitude_m=80,
            speed_mps=10,
            battery_pct=battery,
            gps_satellites=14,
            heading_deg=0,
            status="FLYING",
        ),
    )


def latest_battery(store: TelemetryStore) -> int:
    row = store.conn.execute(
        "SELECT battery_pct FROM drone_latest_state WHERE drone_id = 'SF-PN-001'"
    ).fetchone()
    return row[0]


def history_count(store: TelemetryStore) -> int:
    return store.conn.execute("SELECT count(*) FROM telemetry_history").fetchone()[0]


def test_new_message_is_stored_everywhere(store):
    assert store.save(make_env(5, 89)) == (True, True)
    assert latest_battery(store) == 89


def test_duplicate_is_ignored(store):
    env = make_env(5, 89)
    store.save(env)
    assert store.save(env) == (False, False)
    assert history_count(store) == 1


def test_late_message_kept_in_history_but_not_latest(store):
    store.save(make_env(5, 89))
    assert store.save(make_env(2, 91)) == (True, False)
    assert latest_battery(store) == 89
    assert history_count(store) == 2


def test_newer_message_updates_latest(store):
    store.save(make_env(5, 89))
    assert store.save(make_env(8, 88)) == (True, True)
    assert latest_battery(store) == 88
