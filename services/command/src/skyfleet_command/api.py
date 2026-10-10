import os
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import Depends, FastAPI, Header, HTTPException, Request, Response
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool
from pydantic import BaseModel, Field, model_validator

from skyfleet_command.store import CommandStore
from skyfleet_contracts import CommandType, Waypoint
from skyfleet_contracts.telemetry import DRONE_ID_PATTERN

COMMAND_TTL_S = 30


class CreateCommand(BaseModel):
    """What an operator sends. Validated before anything touches the database."""

    drone_id: str = Field(pattern=DRONE_ID_PATTERN)
    site_id: str = Field(
        pattern=r"^[A-Z0-9-]{1,32}$"
    )  # no '/', '+', '#': it becomes a topic
    type: CommandType
    target: Waypoint | None = None

    @model_validator(mode="after")
    def check_target(self) -> "CreateCommand":
        if (self.type is CommandType.GOTO) != (self.target is not None):
            raise ValueError("GOTO needs a target; other commands must not have one")
        return self


class CommandView(BaseModel):
    """What the API returns."""

    command_id: UUID
    drone_id: str
    site_id: str
    type: CommandType
    state: str
    attempts: int
    expires_at: datetime
    reason: str | None
    created_at: datetime
    updated_at: datetime


@asynccontextmanager
async def lifespan(app: FastAPI):
    pool = ConnectionPool(
        os.environ["DATABASE_URL"],
        kwargs={"row_factory": dict_row, "autocommit": True},
        open=True,
    )
    app.state.pool = pool
    yield
    pool.close()


app = FastAPI(title="SkyFleet Command API", lifespan=lifespan)


def get_store(request: Request):
    with request.app.state.pool.connection() as conn:
        yield CommandStore(conn)


Store = Annotated[CommandStore, Depends(get_store)]


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.post("/v1/commands", response_model=CommandView, status_code=201)
def create_command(
    body: CreateCommand,
    response: Response,
    store: Store,
    idempotency_key: Annotated[str | None, Header(max_length=100)] = None,
):
    row, created = store.create(
        drone_id=body.drone_id,
        site_id=body.site_id,
        command_type=body.type,
        target=body.target,
        ttl_s=COMMAND_TTL_S,
        idempotency_key=idempotency_key,
    )
    if not created:
        response.status_code = 200
    return row


@app.get("/v1/commands/{command_id}", response_model=CommandView)
def get_command(command_id: UUID, store: Store):
    row = store.get(command_id)
    if row is None:
        raise HTTPException(status_code=404, detail="command not found")
    return row
