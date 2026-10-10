import os
import queue
import time
from datetime import datetime, timezone

import paho.mqtt.client as mqtt
from pydantic import ValidationError

from skyfleet_contracts import CommandAckV1, CommandRequestV1, Envelope
from skyfleet_contracts.topics import (
    command_acks_topic,
    commands_topic,
    status_topic,
    telemetry_topic,
)
from skyfleet_edge.commands import CommandExecutor
from skyfleet_edge.drone import VirtualDrone

MQTT_HOST = os.getenv("MQTT_HOST", "localhost")
MQTT_PORT = int(os.getenv("MQTT_PORT", "1883"))
SITE_ID = os.getenv("SITE_ID", "PUNE-001")
DRONE_ID = os.getenv("DRONE_ID", "SF-PN-001")
TICK_S = float(os.getenv("TICK_S", "1.0"))


def publish_acks(client: mqtt.Client, acks: list[CommandAckV1]) -> None:
    for ack in acks:
        env = Envelope[CommandAckV1](
            event_type="command.ack", producer="edge-simulator", payload=ack
        )
        client.publish(
            command_acks_topic(SITE_ID, DRONE_ID), env.model_dump_json(), qos=1
        )
        print(f"  ack {ack.command_id} {ack.result} {ack.reason or ''}")


def main() -> None:
    drone = VirtualDrone(DRONE_ID, latitude=18.5204, longitude=73.8567)
    drone.fly_to(18.5300, 73.8567)
    executor = CommandExecutor(drone)
    inbox: queue.Queue[CommandRequestV1] = queue.Queue()  # MQTT thread -> main thread

    def on_connect(client, userdata, flags, reason_code, properties):
        if reason_code.is_failure:
            print(f"connect failed: {reason_code}")
            return
        print("connected to broker")
        client.subscribe(commands_topic(SITE_ID, DRONE_ID), qos=1)
        client.publish(status_topic(SITE_ID, DRONE_ID), "online", qos=1, retain=True)

    def on_disconnect(client, userdata, flags, reason_code, properties):
        print(f"disconnected: {reason_code}")

    def on_message(client, userdata, msg):
        try:
            env = Envelope[CommandRequestV1].model_validate_json(msg.payload)
        except ValidationError as e:
            print(f"rejected command message: {e.error_count()} errors")
            return
        inbox.put(env.payload)  # hand it to the main thread; never touch the drone here

    client = mqtt.Client(
        mqtt.CallbackAPIVersion.VERSION2,
        client_id=f"edge-{DRONE_ID}",
        clean_session=False,
    )
    client.on_connect = on_connect
    client.on_disconnect = on_disconnect
    client.on_message = on_message
    client.will_set(status_topic(SITE_ID, DRONE_ID), "offline", qos=1, retain=True)
    client.reconnect_delay_set(min_delay=1, max_delay=10)
    client.connect(MQTT_HOST, MQTT_PORT, keepalive=10)
    client.loop_start()

    try:
        while True:
            now = datetime.now(timezone.utc)
            while not inbox.empty():
                cmd = inbox.get_nowait()
                print(f"command {cmd.command_id} {cmd.type} attempt={cmd.attempt}")
                publish_acks(client, executor.handle(cmd, now))
            drone.step(TICK_S)
            publish_acks(client, executor.tick())
            client.publish(
                telemetry_topic(SITE_ID, DRONE_ID),
                drone.to_telemetry().model_dump_json(),
                qos=1,
            )
            time.sleep(TICK_S)
    except KeyboardInterrupt:
        pass
    finally:
        client.publish(
            status_topic(SITE_ID, DRONE_ID), "offline", qos=1, retain=True
        ).wait_for_publish(timeout=2)
        client.disconnect()
        client.loop_stop()


if __name__ == "__main__":
    main()
