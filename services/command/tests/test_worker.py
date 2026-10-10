import os
from datetime import datetime, timedelta, timezone
from uuid import uuid4

os.environ.setdefault("DATABASE_URL", "unused-in-these-tests")

from skyfleet_command.worker import build_request, decide  # noqa: E402

NOW = datetime(2026, 10, 10, 12, 0, tzinfo=timezone.utc)


def row(**overrides) -> dict:
    data = dict(
        command_id=uuid4(),
        drone_id="SF-PN-001",
        site_id="PUNE-001",
        type="LAND",
        target_lat=None,
        target_lon=None,
        attempts=0,
        expires_at=NOW + timedelta(seconds=30),
    )
    data.update(overrides)
    return data


def test_new_command_is_sent():
    assert decide(row(), NOW, max_attempts=3) == ("send", None)


def test_gives_up_after_max_attempts():
    action, reason = decide(row(attempts=3), NOW, max_attempts=3)
    assert action == "give_up"
    assert "3" in reason


def test_expired_command_is_never_sent():
    action, reason = decide(
        row(expires_at=NOW - timedelta(seconds=1)), NOW, max_attempts=3
    )
    assert action == "give_up"
    assert "expired" in reason


def test_expiry_is_checked_before_attempts():
    expired_and_exhausted = row(attempts=3, expires_at=NOW - timedelta(seconds=1))
    assert "expired" in decide(expired_and_exhausted, NOW, max_attempts=3)[1]


def test_goto_request_carries_target():
    env = build_request(
        row(type="GOTO", target_lat=18.53, target_lon=73.85, attempts=1)
    )
    assert env.payload.target.latitude == 18.53


def test_each_attempt_is_a_new_event_for_the_same_command():
    r = row(attempts=1)
    first, second = build_request(r), build_request(r)
    assert first.event_id != second.event_id
    assert first.payload.command_id == second.payload.command_id
