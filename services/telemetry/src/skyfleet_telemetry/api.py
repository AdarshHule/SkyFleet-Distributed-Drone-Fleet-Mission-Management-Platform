import os
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Annotated

import psycopg
from fastapi import Depends, FastAPI, HTTPException, Query, Request
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool
from pydantic import BaseModel

from skyfleet_contracts import DroneStatus


class DroneState(BaseModel):
    """What the API exposes. Not the DB row, not the MQTT event."""

    drone_id: str
    occurred_at: datetime
    latitude: float
    longitude: float
    altitude_m: float
    speed_mps: float
    battery_pct: int
    gps_satellites: int
    heading_deg: float
    status: DroneStatus


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Runs once at startup and shutdown: one shared pool, not one connection per request.
    pool = ConnectionPool(
        os.environ["DATABASE_URL"], kwargs={"row_factory": dict_row}, open=True
    )
    app.state.pool = pool
    yield
    pool.close()


app = FastAPI(title="SkyFleet Telemetry API", lifespan=lifespan)


def get_conn(request: Request):
    # Borrow a connection for one request, then return it to the pool.
    with request.app.state.pool.connection() as conn:
        yield conn


Conn = Annotated[psycopg.Connection, Depends(get_conn)]


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/v1/drones", response_model=list[DroneState])
def list_drones(conn: Conn):
    return conn.execute(
        """SELECT drone_id, occurred_at, latitude, longitude, altitude_m, speed_mps,
                  battery_pct, gps_satellites, heading_deg, status
           FROM drone_latest_state ORDER BY drone_id"""
    ).fetchall()


@app.get("/v1/drones/{drone_id}", response_model=DroneState)
def get_drone(drone_id: str, conn: Conn):
    row = conn.execute(
        """SELECT drone_id, occurred_at, latitude, longitude, altitude_m, speed_mps,
                  battery_pct, gps_satellites, heading_deg, status
           FROM drone_latest_state
           WHERE drone_id = %s""",
        (drone_id,),
    ).fetchone()

    if row is None:
        raise HTTPException(
            status_code=404,
            detail=f"drone {drone_id} not found",
        )

    return row


@app.get("/v1/drones/{drone_id}/history", response_model=list[DroneState])
def drone_history(
    drone_id: str,
    conn: Conn,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
):
    rows = conn.execute(
        """SELECT drone_id, occurred_at, latitude, longitude, altitude_m, speed_mps,
                  battery_pct, gps_satellites, heading_deg, status
           FROM telemetry_history
           WHERE drone_id = %s
           ORDER BY occurred_at DESC
           LIMIT %s""",
        (drone_id, limit),
    ).fetchall()

    return rows
