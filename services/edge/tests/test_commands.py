from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from skyfleet_contracts import AckResult as A
from skyfleet_contracts import CommandRequestV1, DroneStatus
from skyfleet_edge import geo
from skyfleet_edge.commands import CommandExecutor
from skyfleet_edge.drone import VirtualDrone

NOW = datetime(2026, 10, 10, 12, 0, tzinfo=timezone.utc)
HOME = (18.5204, 73.8567)
NORTH = (18.5300, 73.8567)  # ~1.07 km
EAST = (18.5204, 73.8600)  # ~350 m


def make():
    drone = VirtualDrone("SF-PN-001", latitude=HOME[0], longitude=HOME[1])
    return drone, CommandExecutor(drone)


def cmd(type: str, target=None, **overrides) -> CommandRequestV1:
    data = dict(
        command_id=uuid4(),
        drone_id="SF-PN-001",
        type=type,
        expires_at=NOW + timedelta(seconds=30),
    )
    if target:
        data["target"] = {"latitude": target[0], "longitude": target[1]}
    data.update(overrides)
    return CommandRequestV1(**data)


def results(acks):
    return [a.result for a in acks]


def run_until_complete(drone, ex, max_steps=300):
    for _ in range(max_steps):
        drone.step(1.0)
        acks = ex.tick()
        if acks:
            return acks
    pytest.fail("command never completed")


def test_goto_is_accepted_then_completes_on_arrival():
    drone, ex = make()
    goto = cmd("GOTO", target=EAST)
    assert results(ex.handle(goto, NOW)) == [A.ACCEPTED]
    done = run_until_complete(drone, ex)
    assert [(a.command_id, a.result) for a in done] == [(goto.command_id, A.COMPLETED)]


def test_land_while_flying_completes_immediately():
    drone, ex = make()
    drone.fly_to(*NORTH)
    drone.step(1.0)
    assert results(ex.handle(cmd("LAND"), NOW)) == [A.ACCEPTED, A.COMPLETED]
    assert drone.status is DroneStatus.LANDED


def test_land_on_the_ground_is_rejected():
    drone, ex = make()
    acks = ex.handle(cmd("LAND"), NOW)
    assert results(acks) == [A.REJECTED]
    assert acks[0].reason == "not flying"


def test_expired_command_is_rejected_and_not_executed():
    drone, ex = make()
    acks = ex.handle(
        cmd("GOTO", target=EAST, expires_at=NOW - timedelta(seconds=1)), NOW
    )
    assert results(acks) == [A.REJECTED]
    assert acks[0].reason == "expired"
    assert drone.status is DroneStatus.IDLE


def test_command_for_another_drone_is_rejected():
    drone, ex = make()
    acks = ex.handle(cmd("GOTO", target=EAST, drone_id="SF-PN-002"), NOW)
    assert acks[0].reason == "wrong drone"


def test_late_duplicate_after_completion_does_not_fly_again():
    drone, ex = make()
    goto = cmd("GOTO", target=EAST)
    ex.handle(goto, NOW)
    run_until_complete(drone, ex)
    assert results(ex.handle(goto, NOW)) == [A.COMPLETED]  # the LAST ack, re-sent
    assert drone.status is DroneStatus.LANDED  # not executed again


def test_new_command_supersedes_the_active_one():
    drone, ex = make()
    first, second = cmd("GOTO", target=NORTH), cmd("GOTO", target=EAST)
    ex.handle(first, NOW)
    acks = ex.handle(second, NOW)
    assert [(a.command_id, a.result) for a in acks] == [
        (first.command_id, A.FAILED),
        (second.command_id, A.ACCEPTED),
    ]
    assert "superseded" in acks[0].reason


def test_late_duplicate_cannot_undo_a_newer_command():
    drone, ex = make()
    drone.fly_to(*NORTH)
    for _ in range(20):
        drone.step(1.0)
    go_home = cmd("RETURN_HOME")
    ex.handle(go_home, NOW)
    ex.handle(cmd("GOTO", target=EAST), NOW)  # operator changes their mind
    assert results(ex.handle(go_home, NOW)) == [
        A.FAILED
    ]  # delayed retry of RETURN_HOME
    assert drone.target == EAST  # still going east, not home
    assert drone.status is DroneStatus.FLYING


def test_return_home_flies_back_and_lands():
    drone, ex = make()
    drone.fly_to(*NORTH)
    for _ in range(20):
        drone.step(1.0)
    ex.handle(cmd("RETURN_HOME"), NOW)
    assert drone.status is DroneStatus.RETURNING
    run_until_complete(drone, ex)
    assert geo.distance_m(drone.latitude, drone.longitude, *HOME) < 1.0
