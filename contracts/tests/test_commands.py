from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from pydantic import ValidationError

from skyfleet_contracts import CommandRequestV1, CommandType
from skyfleet_contracts.topics import command_acks_topic

LATER = datetime.now(timezone.utc) + timedelta(seconds=30)


def request(**overrides):
    data = dict(command_id=uuid4(), drone_id="SF-PN-001", type="LAND", expires_at=LATER)
    data.update(overrides)
    return CommandRequestV1(**data)


def test_land_without_target_is_valid():
    assert request().type is CommandType.LAND


def test_goto_with_target_is_valid():
    cmd = request(type="GOTO", target={"latitude": 18.53, "longitude": 73.85})
    assert cmd.target.latitude == 18.53


@pytest.mark.parametrize(
    "overrides",
    [
        {"type": "GOTO"},  # GOTO needs a target
        {
            "type": "LAND",
            "target": {"latitude": 1, "longitude": 1},
        },  # LAND must not have one
        {"expires_at": datetime(2026, 10, 10, 12, 0)},  # naive datetime
        {"attempt": 0},
        {"drone_id": "drone-1"},
    ],
)
def test_invalid_requests_rejected(overrides):
    with pytest.raises(ValidationError):
        request(**overrides)


def test_command_acks_topic():
    assert (
        command_acks_topic("PUNE-001", "SF-PN-001")
        == "skyfleet/PUNE-001/SF-PN-001/command_acks"
    )
