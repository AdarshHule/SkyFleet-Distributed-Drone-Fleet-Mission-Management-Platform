import os
import time
from datetime import datetime, timezone

import paho.mqtt.client as mqtt
from pydantic import ValidationError

from skyfleet_command.state import InvalidTransition
from skyfleet_command.store import CommandStore, connect
from skyfleet_contracts import CommandAckV1, CommandRequestV1, Envelope, Waypoint
from skyfleet_contracts.topics import commands_topic

MQTT_HOST = os.getenv("MQTT_HOST", "localhost")
MQTT_PORT = int(os.getenv("MQTT_PORT", "1883"))
DATABASE_URL = os.environ["DATABASE_URL"]
POLL_S = 0.5
RETRY_AFTER_S = 5
MAX_ATTEMPTS = 3
ACK_SUBSCRIPTION = "skyfleet/+/+/command_acks"


def decide(row: dict, now: datetime, max_attempts: int) -> tuple[str, str | None]:
    """What to do with a due command: ("send", None) or ("give_up", reason).

    Pure function: no database, no MQTT, easy to test.
    """
    if now >= row["expires_at"]:
        return "give_up", "expired before delivery"

    if row["attempts"] >= max_attempts:
        return "give_up", f"no ack after {row['attempts']} attempts"

    return "send", None


def build_request(row: dict) -> Envelope[CommandRequestV1]:
    target = None
    if row["target_lat"] is not None:
        target = Waypoint(latitude=row["target_lat"], longitude=row["target_lon"])
    return Envelope[CommandRequestV1](
        event_type="command.requested",
        producer="command-worker",
        payload=CommandRequestV1(
            command_id=row["command_id"],
            drone_id=row["drone_id"],
            type=row["type"],
            target=target,
            attempt=row["attempts"],
            expires_at=row["expires_at"],
        ),
    )


def main() -> None:
    send_store = CommandStore(connect(DATABASE_URL))  # main thread only
    ack_store = CommandStore(connect(DATABASE_URL))  # MQTT thread only

    def on_connect(client, userdata, flags, reason_code, properties):
        if reason_code.is_failure:
            print(f"connect failed: {reason_code}")
            return
        client.subscribe(ACK_SUBSCRIPTION, qos=1)
        print(f"subscribed to {ACK_SUBSCRIPTION}")

    def on_message(client, userdata, msg):
        try:
            env = Envelope[CommandAckV1].model_validate_json(msg.payload)
        except ValidationError as e:
            print(f"rejected ack on {msg.topic}: {e.error_count()} errors")
            return
        ack = env.payload
        try:
            changed = ack_store.record_ack(ack)
        except InvalidTransition as e:
            print(f"ignored impossible ack: {e}")
            return
        print(f"ack {ack.command_id} {ack.result} changed={changed}")

    client = mqtt.Client(
        mqtt.CallbackAPIVersion.VERSION2,
        client_id="command-worker",
        clean_session=False,
    )
    client.on_connect = on_connect
    client.on_message = on_message
    client.reconnect_delay_set(min_delay=1, max_delay=10)
    client.connect(MQTT_HOST, MQTT_PORT, keepalive=30)
    client.loop_start()

    try:
        while True:
            now = datetime.now(timezone.utc)
            for row in send_store.due_for_send():
                command_id = row["command_id"]
                action, reason = decide(row, now, MAX_ATTEMPTS)
                try:
                    if action == "give_up":
                        if send_store.give_up(command_id, reason):
                            print(f"gave up {command_id}: {reason}")
                        continue
                    sent = send_store.mark_sent(command_id, RETRY_AFTER_S)  # 1. save...
                except InvalidTransition:
                    continue  # an ack changed the state since we read it: skip
                if sent is None:
                    continue
                client.publish(  # 2. ...then publish
                    commands_topic(sent["site_id"], sent["drone_id"]),
                    build_request(sent).model_dump_json(),
                    qos=1,
                )
                print(f"sent {command_id} {sent['type']} attempt={sent['attempts']}")
            time.sleep(POLL_S)
    except KeyboardInterrupt:
        pass
    finally:
        client.loop_stop()
        client.disconnect()


if __name__ == "__main__":
    main()
