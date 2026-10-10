import sys
from uuid import UUID

import paho.mqtt.publish as publish

from skyfleet_contracts import CommandAckV1, Envelope
from skyfleet_contracts.topics import command_acks_topic

command_id, result = sys.argv[1], sys.argv[2]
env = Envelope[CommandAckV1](
    event_type="command.ack",
    producer="fake-drone",
    payload=CommandAckV1(
        command_id=UUID(command_id), drone_id="SF-PN-001", result=result
    ),
)
publish.single(
    command_acks_topic("PUNE-001", "SF-PN-001"),
    env.model_dump_json(),
    qos=1,
    hostname="localhost",
)
print(f"sent {result} for {command_id}")
