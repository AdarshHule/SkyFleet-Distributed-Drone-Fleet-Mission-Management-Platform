import json

from skyfleet_contracts import Envelope, TelemetryV1
from skyfleet_gateway.live import to_live_message


def make_payload() -> bytes:
    env = Envelope[TelemetryV1](
        event_type="drone.telemetry",
        producer="test",
        payload=TelemetryV1(
            drone_id="SF-PN-001",
            latitude=18.52,
            longitude=73.85,
            altitude_m=80,
            speed_mps=10,
            battery_pct=97,
            gps_satellites=14,
            heading_deg=0,
            status="FLYING",
        ),
    )
    return env.model_dump_json().encode()


def test_valid_message_is_converted():
    out = json.loads(to_live_message(make_payload()))
    assert out["drone_id"] == "SF-PN-001"
    assert out["battery_pct"] == 97
    assert out["status"] == "FLYING"
    assert "occurred_at" in out


def test_internal_fields_are_not_sent_to_browsers():
    out = json.loads(to_live_message(make_payload()))
    assert "event_id" not in out
    assert "producer" not in out


def test_garbage_is_never_forwarded():
    assert to_live_message(b"garbage") is None
