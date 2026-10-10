import os

import pytest
from fastapi.testclient import TestClient

from skyfleet_command.api import app
from skyfleet_command.store import connect

TEST_DB_URL = os.getenv(
    "TEST_DATABASE_URL",
    "postgresql://skyfleet:change-me-local-only@localhost:5432/skyfleet_command_test",
)
LAND = {"drone_id": "SF-PN-001", "site_id": "PUNE-001", "type": "LAND"}


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", TEST_DB_URL)
    with connect(TEST_DB_URL) as conn:
        conn.execute("TRUNCATE commands")
    with TestClient(app) as c:
        yield c


def test_create_returns_201_and_pending(client):
    r = client.post("/v1/commands", json=LAND)
    assert r.status_code == 201
    assert r.json()["state"] == "PENDING"


def test_same_idempotency_key_replays_the_same_command(client):
    headers = {"Idempotency-Key": "click-1"}
    a = client.post("/v1/commands", json=LAND, headers=headers)
    b = client.post("/v1/commands", json=LAND, headers=headers)
    assert (a.status_code, b.status_code) == (201, 200)
    assert a.json()["command_id"] == b.json()["command_id"]


def test_get_command(client):
    created = client.post("/v1/commands", json=LAND).json()
    r = client.get(f"/v1/commands/{created['command_id']}")
    assert r.status_code == 200
    assert r.json()["type"] == "LAND"


def test_unknown_command_is_404(client):
    assert (
        client.get("/v1/commands/00000000-0000-0000-0000-000000000000").status_code
        == 404
    )


@pytest.mark.parametrize(
    "body",
    [
        {**LAND, "type": "GOTO"},  # GOTO without target
        {**LAND, "target": {"latitude": 18.5, "longitude": 73.8}},  # LAND with target
        {**LAND, "site_id": "PUNE/001"},  # topic injection
        {**LAND, "drone_id": "drone-1"},
    ],
)
def test_invalid_bodies_are_422(client, body):
    assert client.post("/v1/commands", json=body).status_code == 422
