import pytest

from skyfleet_contracts import DroneStatus
from skyfleet_edge import geo
from skyfleet_edge.drone import VirtualDrone

START = (18.5204, 73.8567)
TARGET_NORTH = (18.5300, 73.8567)  # about 1.07 km north


def make_drone() -> VirtualDrone:
    return VirtualDrone("SF-PN-001", latitude=START[0], longitude=START[1])


def test_idle_drone_does_not_move():
    d = make_drone()
    d.step(1.0)
    assert (d.latitude, d.longitude) == START
    assert d.battery_pct == 100.0


def test_flying_drone_moves_10m_per_second():
    d = make_drone()
    d.fly_to(*TARGET_NORTH)
    before = geo.distance_m(d.latitude, d.longitude, *TARGET_NORTH)
    d.step(1.0)
    after = geo.distance_m(d.latitude, d.longitude, *TARGET_NORTH)
    assert before - after == pytest.approx(10.0, abs=0.1)


def test_heading_points_north():
    d = make_drone()
    d.fly_to(*TARGET_NORTH)
    d.step(1.0)
    assert d.heading_deg == pytest.approx(0.0, abs=0.5)


def test_battery_drains_while_flying():
    d = make_drone()
    d.fly_to(*TARGET_NORTH)
    for _ in range(10):
        d.step(1.0)
    assert d.battery_pct == pytest.approx(99.5)


def test_battery_never_goes_negative():
    d = make_drone()
    d.battery_pct = 0.01
    d.fly_to(*TARGET_NORTH)
    d.step(10.0)
    assert d.battery_pct == 0.0


def test_drone_lands_at_target():
    d = make_drone()
    d.fly_to(*TARGET_NORTH)
    for _ in range(200):  # ~107 s needed at 10 m/s
        d.step(1.0)
    assert d.status is DroneStatus.LANDED
    assert d.speed_mps == 0
    assert d.target is None


def test_telemetry_matches_contract():
    d = make_drone()
    d.fly_to(*TARGET_NORTH)
    d.step(1.0)
    env = d.to_telemetry()
    assert env.event_type == "drone.telemetry"
    assert env.producer == "edge-simulator"
    assert env.payload.drone_id == "SF-PN-001"
    assert env.payload.status is DroneStatus.FLYING