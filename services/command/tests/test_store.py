import os
from uuid import uuid4

import pytest

from skyfleet_command.store import CommandStore, connect
from skyfleet_contracts import CommandAckV1, CommandType

TEST_DB_URL = os.getenv(
    "TEST_DATABASE_URL",
    "postgresql://skyfleet:change-me-local-only@localhost:5432/skyfleet_command_test",
)
LAND = dict(
    drone_id="SF-PN-001",
    site_id="PUNE-001",
    command_type=CommandType.LAND,
    target=None,
    ttl_s=30,
)


@pytest.fixture
def store():
    with connect(TEST_DB_URL) as conn:
        conn.execute("TRUNCATE commands")
        yield CommandStore(conn)


def ack(command_id, result: str) -> CommandAckV1:
    return CommandAckV1(command_id=command_id, drone_id="SF-PN-001", result=result)


def sent_command(store) -> dict:
    cmd, _ = store.create(**LAND)
    store.mark_sent(cmd["command_id"], retry_after_s=5)
    return cmd


def test_same_idempotency_key_returns_existing_command(store):
    a, created_a = store.create(**LAND, idempotency_key="click-1")
    b, created_b = store.create(**LAND, idempotency_key="click-1")
    assert created_a and not created_b
    assert a["command_id"] == b["command_id"]


def test_without_key_every_create_is_new(store):
    a, _ = store.create(**LAND)
    b, _ = store.create(**LAND)
    assert a["command_id"] != b["command_id"]


def test_mark_sent_counts_attempts(store):
    cmd, _ = store.create(**LAND)
    store.mark_sent(cmd["command_id"], retry_after_s=5)
    row = store.mark_sent(cmd["command_id"], retry_after_s=5)
    assert row["state"] == "SENT"
    assert row["attempts"] == 2


def test_accepted_ack_stops_retries(store):
    cmd = sent_command(store)
    assert store.record_ack(ack(cmd["command_id"], "ACCEPTED"))
    row = store.get(cmd["command_id"])
    assert row["state"] == "ACCEPTED"
    assert row["next_attempt_at"] is None


def test_duplicate_ack_is_ignored(store):
    cmd = sent_command(store)
    store.record_ack(ack(cmd["command_id"], "ACCEPTED"))
    assert store.record_ack(ack(cmd["command_id"], "ACCEPTED")) is False


def test_ack_for_unknown_command_is_ignored(store):
    assert store.record_ack(ack(uuid4(), "COMPLETED")) is False


def test_due_for_retry_only_returns_overdue_commands(store):
    overdue, _ = store.create(**LAND)
    waiting, _ = store.create(**LAND)
    store.mark_sent(overdue["command_id"], retry_after_s=0)
    store.mark_sent(waiting["command_id"], retry_after_s=60)
    due = {row["command_id"] for row in store.due_for_retry()}
    assert due == {overdue["command_id"]}


def test_late_ack_after_give_up_is_ignored(store):
    cmd = sent_command(store)
    assert store.give_up(cmd["command_id"], "no ack after 3 attempts")
    assert store.record_ack(ack(cmd["command_id"], "COMPLETED")) is False
    assert store.get(cmd["command_id"])["state"] == "TIMED_OUT"


def test_cannot_resend_a_finished_command(store):
    cmd = sent_command(store)
    store.record_ack(ack(cmd["command_id"], "REJECTED"))
    assert store.mark_sent(cmd["command_id"], retry_after_s=5) is None


def test_due_for_send_includes_new_and_overdue_commands(store):
    new, _ = store.create(**LAND)
    overdue, _ = store.create(**LAND)
    waiting, _ = store.create(**LAND)
    store.mark_sent(overdue["command_id"], retry_after_s=0)
    store.mark_sent(waiting["command_id"], retry_after_s=60)
    due = {row["command_id"] for row in store.due_for_send()}
    assert due == {new["command_id"], overdue["command_id"]}
