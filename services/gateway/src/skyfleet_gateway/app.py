import asyncio
import os
from contextlib import asynccontextmanager
from typing import Annotated
from uuid import UUID

import httpx
from fastapi import (
    Body,
    FastAPI,
    Header,
    HTTPException,
    Path,
    Query,
    Request,
    Response,
    WebSocket,
    WebSocketDisconnect,
)

from skyfleet_gateway.live import Hub, mqtt_listener

TELEMETRY_URL = os.getenv("TELEMETRY_URL", "http://localhost:8001")
COMMAND_URL = os.getenv("COMMAND_URL", "http://localhost:8002")
TIMEOUT_S = 2.0
DRONE_ID_PATTERN = r"^SF-[A-Z]{2}-\d{3}$"

DroneId = Annotated[str, Path(pattern=DRONE_ID_PATTERN)]


def create_app(
    transport: httpx.AsyncBaseTransport | None = None, start_mqtt: bool = True
) -> FastAPI:
    """Build the app. Tests pass a fake transport and start_mqtt=False."""

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.telemetry = httpx.AsyncClient(
            base_url=TELEMETRY_URL, timeout=TIMEOUT_S, transport=transport
        )
        app.state.command = httpx.AsyncClient(
            base_url=COMMAND_URL, timeout=TIMEOUT_S, transport=transport
        )
        app.state.hub = Hub()
        task = asyncio.create_task(mqtt_listener(app.state.hub)) if start_mqtt else None
        yield
        if task:
            task.cancel()
        await app.state.telemetry.aclose()
        await app.state.command.aclose()

    app = FastAPI(title="SkyFleet API Gateway", lifespan=lifespan)

    async def call_upstream(
        client: httpx.AsyncClient,
        name: str,
        method: str,
        path: str,
        *,
        params: dict | None = None,
        json: dict | None = None,
        headers: dict | None = None,
    ) -> httpx.Response:
        try:
            response = await client.request(
                method, path, params=params, json=json, headers=headers
            )
        except httpx.TimeoutException as exc:
            raise HTTPException(
                status_code=504,
                detail=f"{name} service timed out",
            ) from exc
        except httpx.TransportError as exc:
            raise HTTPException(
                status_code=503,
                detail=f"{name} service unavailable",
            ) from exc

        if response.status_code in (404, 422):
            raise HTTPException(
                status_code=response.status_code,
                detail=response.json().get("detail", "request rejected"),
            )
        if response.status_code >= 400:
            raise HTTPException(
                status_code=502,
                detail=f"{name} service error",
            )
        return response

    async def call_telemetry(
        request: Request,
        path: str,
        params: dict | None = None,
    ):
        response = await call_upstream(
            request.app.state.telemetry,
            "telemetry",
            "GET",
            path,
            params=params,
        )
        return response.json()

    @app.get("/health")
    async def health() -> dict:
        return {"status": "ok"}

    @app.get("/api/v1/drones")
    async def list_drones(request: Request):
        return await call_telemetry(request, "/v1/drones")

    @app.get("/api/v1/drones/{drone_id}")
    async def get_drone(request: Request, drone_id: DroneId):
        return await call_telemetry(request, f"/v1/drones/{drone_id}")

    @app.get("/api/v1/drones/{drone_id}/history")
    async def drone_history(
        request: Request,
        drone_id: DroneId,
        limit: Annotated[int, Query(ge=1, le=500)] = 100,
    ):
        return await call_telemetry(
            request, f"/v1/drones/{drone_id}/history", params={"limit": limit}
        )

    @app.post("/api/v1/commands")
    async def create_command(
        request: Request,
        response: Response,
        body: Annotated[dict, Body()],
        idempotency_key: Annotated[str | None, Header(max_length=100)] = None,
    ):
        headers = {"Idempotency-Key": idempotency_key} if idempotency_key else None
        upstream = await call_upstream(
            request.app.state.command,
            "command",
            "POST",
            "/v1/commands",
            json=body,
            headers=headers,
        )
        response.status_code = upstream.status_code
        return upstream.json()

    @app.get("/api/v1/commands/{command_id}")
    async def get_command(request: Request, command_id: UUID):
        response = await call_upstream(
            request.app.state.command,
            "command",
            "GET",
            f"/v1/commands/{command_id}",
        )
        return response.json()

    @app.websocket("/ws/telemetry")
    async def ws_telemetry(ws: WebSocket):
        hub: Hub = ws.app.state.hub
        await hub.connect(ws)
        try:
            while True:
                await (
                    ws.receive_text()
                )  # we don't expect messages; this detects disconnects
        except WebSocketDisconnect:
            hub.disconnect(ws)

    return app


app = create_app()
