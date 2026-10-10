"""Canonical MQTT topic builders for SkyFleet."""


def _topic(site_id: str, drone_id: str, kind: str) -> str:
    """Validate IDs and build a topic."""
    for name, value in (("site_id", site_id), ("drone_id", drone_id)):
        if not value or any(char in value for char in "/+#"):
            raise ValueError(
                f"{name} must be non-empty and cannot contain '/', '+' or '#'"
            )

    return f"skyfleet/{site_id}/{drone_id}/{kind}"


def telemetry_topic(site_id: str, drone_id: str) -> str:
    return _topic(site_id, drone_id, "telemetry")


def commands_topic(site_id: str, drone_id: str) -> str:
    return _topic(site_id, drone_id, "commands")


def command_acks_topic(site_id: str, drone_id: str) -> str:
    return _topic(site_id, drone_id, "command_acks")


def status_topic(site_id: str, drone_id: str) -> str:
    return _topic(site_id, drone_id, "status")
