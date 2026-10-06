from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pytest
from pydantic import ValidationError
from skyfleet_contracts import DroneStatus, Envelope, TelemetryV1


def valid(**overrides):
    data = {
        "drone_id": "SF-PN-001",
        "latitude": 18.5204,
        "longitude": 73.8567,
        "altitude_m": 84.3,
        "speed_mps": 11.4,
        "battery_pct": 78,
        "gps_satellites": 14,
        "heading_deg": 270.0,
        "status": "FLYING",
    }
    data.update(overrides)
    return data


def test_valid_telemetry_parses():
    t = TelemetryV1(**valid())
    assert t.status is DroneStatus.FLYING


@pytest.mark.parametrize(
    "field,value",
    [
        ("battery_pct", 101),
        ("battery_pct", -1),
        ("latitude", 91),
        ("longitude", -181),
        ("heading_deg", 360),
        ("speed_mps", -0.1),
        ("drone_id", "drone-1"),
        ("status", "OFFLINE"),
    ],
)
def test_invalid_values_rejected(field, value):
    with pytest.raises(ValidationError):
        TelemetryV1(**valid(**{field: value}))


def test_unknown_fields_are_ignored():
    t = TelemetryV1(**valid(temperature_c=41.0))
    assert not hasattr(t, "temperature_c")


def test_envelope_round_trip():
    env = Envelope[TelemetryV1](
        event_type="drone.telemetry",
        producer="simulator",
        payload=TelemetryV1(**valid()),
    )
    back = Envelope[TelemetryV1].model_validate_json(env.model_dump_json())
    assert back == env
    assert back.occurred_at.tzinfo is not None


def test_naive_datetime_rejected():
    # A "naive" datetime has no timezone, so we can't know if it's IST, UTC or anything else.
    naive_time = datetime(2026, 10, 6, 10, 0)  # noqa: DTZ001 - naive on purpose

    with pytest.raises(ValidationError):
        Envelope[TelemetryV1](
            event_type="drone.telemetry",
            producer="simulator",
            occurred_at=naive_time,
            payload=TelemetryV1(**valid()),
        )


def test_ist_time_converted_to_utc():
    # 10:00 in India (UTC+05:30) is 04:30 UTC.
    ist_time = datetime(2026, 10, 6, 10, 0, tzinfo=ZoneInfo("Asia/Kolkata"))

    env = Envelope[TelemetryV1](
        event_type="drone.telemetry",
        producer="simulator",
        occurred_at=ist_time,
        payload=TelemetryV1(**valid()),
    )

    assert env.occurred_at.hour == 4
    assert env.occurred_at.minute == 30
    assert env.occurred_at.utcoffset() == timedelta(0)  # really stored as UTC
