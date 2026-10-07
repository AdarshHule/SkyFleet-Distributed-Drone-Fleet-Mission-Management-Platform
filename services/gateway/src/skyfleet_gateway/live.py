import asyncio
import json
import os

import aiomqtt
from fastapi import WebSocket
from pydantic import ValidationError

from skyfleet_contracts import Envelope, TelemetryV1

MQTT_HOST = os.getenv("MQTT_HOST", "localhost")
MQTT_PORT = int(os.getenv("MQTT_PORT", "1883"))
SUBSCRIPTION = "skyfleet/+/+/telemetry"


def to_live_message(payload: bytes) -> str | None:
    """Turn a raw MQTT payload into the JSON we send to browsers.

    Returns None for invalid messages, so they are never forwarded.
    """
    try:
        env = Envelope[TelemetryV1].model_validate_json(payload)
    except ValidationError:
        return None

    live_message = {
        "occurred_at": env.occurred_at.isoformat(),
        **env.payload.model_dump(mode="json"),
    }
    return json.dumps(live_message)


class Hub:
    """Keeps track of connected browsers and sends each message to all of them."""

    def __init__(self) -> None:
        self.clients: set[WebSocket] = set()

    async def connect(self, ws: WebSocket) -> None:
        await ws.accept()
        self.clients.add(ws)

    def disconnect(self, ws: WebSocket) -> None:
        self.clients.discard(ws)

    async def broadcast(self, text: str) -> None:
        for ws in list(self.clients):
            try:
                await ws.send_text(text)
            except Exception:
                self.disconnect(ws)  # browser went away: forget it


async def mqtt_listener(hub: Hub) -> None:
    """Runs forever in the background: MQTT in, WebSocket out. Reconnects on failure."""
    while True:
        try:
            async with aiomqtt.Client(hostname=MQTT_HOST, port=MQTT_PORT) as client:
                await client.subscribe(SUBSCRIPTION, qos=0)
                print(f"live view subscribed to {SUBSCRIPTION}")
                async for message in client.messages:
                    text = to_live_message(message.payload)
                    if text is not None:
                        await hub.broadcast(text)
        except aiomqtt.MqttError as e:
            print(f"live view lost MQTT ({e}), retrying in 2s")
            await asyncio.sleep(2)
