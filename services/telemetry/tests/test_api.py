import os
from datetime import datetime, timedelta, timezone

import psycopg
import pytest
from fastapi.testclient import TestClient

from skyfleet_contracts import Envelope, TelemetryV1
from skyfleet_telemetry.api import app
from skyfleet_telemetry.store import TelemetryStore

TEST_DB_URL = os.getenv(
    "TEST_DATABASE_URL",
    "postgresql://skyfleet:change-me-local-only@localhost:5432/skyfleet_test",
)
T0 = datetime(2026, 10, 7, 10, 0, tzinfo=timezone.utc)


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


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", TEST_DB_URL)
    with psycopg.connect(TEST_DB_URL, autocommit=True) as conn:
        conn.execute("TRUNCATE telemetry_history, drone_latest_state")
        store = TelemetryStore(conn)
        for seconds, battery in [(1, 99), (2, 98), (3, 97)]:
            store.save(make_env(seconds, battery))
    with TestClient(app) as c:
        yield c


def test_health(client):
    assert client.get("/health").json() == {"status": "ok"}


def test_list_drones_shows_latest_state(client):
    drones = client.get("/v1/drones").json()
    assert len(drones) == 1
    assert drones[0]["battery_pct"] == 97


def test_get_drone(client):
    response = client.get("/v1/drones/SF-PN-001")
    assert response.status_code == 200
    assert response.json()["drone_id"] == "SF-PN-001"


def test_unknown_drone_is_404(client):
    assert client.get("/v1/drones/SF-XX-999").status_code == 404


def test_history_is_newest_first_and_limited(client):
    rows = client.get("/v1/drones/SF-PN-001/history?limit=2").json()
    assert [r["battery_pct"] for r in rows] == [97, 98]


@pytest.mark.parametrize("limit", [0, 501])
def test_history_limit_is_validated(client, limit):
    response = client.get(f"/v1/drones/SF-PN-001/history?limit={limit}")
    assert response.status_code == 422
