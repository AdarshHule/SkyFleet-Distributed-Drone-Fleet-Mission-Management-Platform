import os
import time

import paho.mqtt.client as mqtt

from skyfleet_contracts.topics import status_topic, telemetry_topic
from skyfleet_edge.drone import VirtualDrone

MQTT_HOST = os.getenv("MQTT_HOST", "localhost")
MQTT_PORT = int(os.getenv("MQTT_PORT", "1883"))
SITE_ID = os.getenv("SITE_ID", "PUNE-001")
DRONE_ID = os.getenv("DRONE_ID", "SF-PN-001")
TICK_S = float(os.getenv("TICK_S", "1.0"))


def on_connect(client, userdata, flags, reason_code, properties):
    if reason_code.is_failure:
        print(f"connect failed: {reason_code}")
        return
    print("connected to broker")
    client.publish(status_topic(SITE_ID, DRONE_ID), "online", qos=1, retain=True)


def on_disconnect(client, userdata, flags, reason_code, properties):
    print(f"disconnected: {reason_code}")


def main() -> None:
    drone = VirtualDrone(DRONE_ID, latitude=18.5204, longitude=73.8567)
    drone.fly_to(18.5300, 73.8567)

    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=f"edge-{DRONE_ID}")
    client.on_connect = on_connect
    client.on_disconnect = on_disconnect
    client.will_set(status_topic(SITE_ID, DRONE_ID), "offline", qos=1, retain=True)
    client.reconnect_delay_set(min_delay=1, max_delay=10)
    client.connect(MQTT_HOST, MQTT_PORT, keepalive=10)
    client.loop_start()

    try:
        while True:
            drone.step(TICK_S)
            info = client.publish(
                telemetry_topic(SITE_ID, DRONE_ID),
                drone.to_telemetry().model_dump_json(),
                qos=1,
            )
            print(f"published rc={info.rc} battery={drone.battery_pct:.2f}")
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
