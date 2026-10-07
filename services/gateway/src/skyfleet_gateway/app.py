import os
from contextlib import asynccontextmanager
from typing import Annotated

import httpx
from fastapi import FastAPI, HTTPException, Path, Query, Request

TELEMETRY_URL = os.getenv("TELEMETRY_URL", "http://localhost:8001")
TIMEOUT_S = 2.0
DRONE_ID_PATTERN = r"^SF-[A-Z]{2}-\d{3}$"

DroneId = Annotated[str, Path(pattern=DRONE_ID_PATTERN)]


def create_app(transport: httpx.AsyncBaseTransport | None = None) -> FastAPI:
    """Build the app. Tests pass a fake transport; production passes nothing."""

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.telemetry = httpx.AsyncClient(
            base_url=TELEMETRY_URL, timeout=TIMEOUT_S, transport=transport
        )
        yield
        await app.state.telemetry.aclose()

    app = FastAPI(title="SkyFleet API Gateway", lifespan=lifespan)

    async def call_telemetry(
        request: Request,
        path: str,
        params: dict | None = None,
    ):
        client: httpx.AsyncClient = request.app.state.telemetry

        try:
            response = await client.get(path, params=params)
        except httpx.TimeoutException as exc:
            raise HTTPException(
                status_code=504,
                detail="telemetry service timed out",
            ) from exc
        except httpx.TransportError as exc:
            raise HTTPException(
                status_code=503,
                detail="telemetry service unavailable",
            ) from exc

        if response.status_code == 404:
            raise HTTPException(
                status_code=404,
                detail=response.json().get("detail", "not found"),
            )

        if response.status_code >= 400:
            raise HTTPException(
                status_code=502,
                detail="telemetry service error",
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

    return app


app = create_app()
