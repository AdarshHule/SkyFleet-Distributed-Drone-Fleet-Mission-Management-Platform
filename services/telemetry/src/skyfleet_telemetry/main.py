import os

import paho.mqtt.client as mqtt
from pydantic import ValidationError

from skyfleet_contracts import Envelope, TelemetryV1
from skyfleet_telemetry.store import TelemetryStore, connect

MQTT_HOST = os.getenv("MQTT_HOST", "localhost")
MQTT_PORT = int(os.getenv("MQTT_PORT", "1883"))
DATABASE_URL = os.environ["DATABASE_URL"]  # required: crash at startup if missing
SUBSCRIPTION = "skyfleet/+/+/telemetry"


def main() -> None:
    store = TelemetryStore(connect(DATABASE_URL))

    def on_connect(client, userdata, flags, reason_code, properties):
        if reason_code.is_failure:
            print(f"connect failed: {reason_code}")
            return
        client.subscribe(SUBSCRIPTION, qos=1)
        print(f"subscribed to {SUBSCRIPTION}")

    def on_message(client, userdata, msg):
        try:
            env = Envelope[TelemetryV1].model_validate_json(msg.payload)
        except ValidationError as e:
            print(f"rejected topic={msg.topic} errors={e.error_count()}")
            return

        inserted, updated = store.save(env)
        print(
            f"drone={env.payload.drone_id} "
            f"occurred_at={env.occurred_at:%H:%M:%S} "
            f"inserted={inserted} updated={updated}"
        )

    client = mqtt.Client(
        mqtt.CallbackAPIVersion.VERSION2,
        client_id="telemetry-service",
        clean_session=False,
    )
    client.on_connect = on_connect
    client.on_message = on_message
    client.reconnect_delay_set(min_delay=1, max_delay=10)
    client.connect(MQTT_HOST, MQTT_PORT, keepalive=30)
    try:
        client.loop_forever()
    except KeyboardInterrupt:
        client.disconnect()


if __name__ == "__main__":
    main()
