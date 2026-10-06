import pytest

from skyfleet_contracts.topics import commands_topic, status_topic, telemetry_topic


def test_topics_are_built_correctly():
    assert (
        telemetry_topic("PUNE-001", "SF-PN-001")
        == "skyfleet/PUNE-001/SF-PN-001/telemetry"
    )
    assert (
        commands_topic("PUNE-001", "SF-PN-001")
        == "skyfleet/PUNE-001/SF-PN-001/commands"
    )
    assert status_topic("PUNE-001", "SF-PN-001") == "skyfleet/PUNE-001/SF-PN-001/status"


@pytest.mark.parametrize(
    "site_id,drone_id",
    [
        ("PUNE/001", "SF-PN-001"),
        ("PUNE-001", "#"),
        ("+", "SF-PN-001"),
        ("", "SF-PN-001"),
    ],
)
def test_unsafe_ids_rejected(site_id, drone_id):
    with pytest.raises(ValueError):
        telemetry_topic(site_id, drone_id)
