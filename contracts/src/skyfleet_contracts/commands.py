from enum import StrEnum
from uuid import UUID

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, model_validator

from skyfleet_contracts.telemetry import DRONE_ID_PATTERN


class CommandType(StrEnum):
    GOTO = "GOTO"
    RETURN_HOME = "RETURN_HOME"
    LAND = "LAND"


class Waypoint(BaseModel):
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)


class CommandRequestV1(BaseModel):
    """Cloud -> drone."""

    model_config = ConfigDict(extra="ignore")

    command_id: UUID
    drone_id: str = Field(pattern=DRONE_ID_PATTERN)
    type: CommandType
    target: Waypoint | None = None
    attempt: int = Field(default=1, ge=1)
    expires_at: AwareDatetime  # rejects naive datetimes automatically

    @model_validator(mode="after")
    def check_target(self) -> "CommandRequestV1":
        if self.type is CommandType.GOTO and self.target is None:
            raise ValueError("GOTO requires a target")
        if self.type is not CommandType.GOTO and self.target is not None:
            raise ValueError(f"{self.type} does not take a target")
        return self


class AckResult(StrEnum):
    ACCEPTED = "ACCEPTED"  # "I will do it"
    REJECTED = "REJECTED"  # "I won't" (expired, invalid for my state, ...)
    COMPLETED = "COMPLETED"  # "done"
    FAILED = "FAILED"  # "I tried and couldn't"


class CommandAckV1(BaseModel):
    """Drone -> cloud."""

    model_config = ConfigDict(extra="ignore")

    command_id: UUID
    drone_id: str = Field(pattern=DRONE_ID_PATTERN)
    result: AckResult
    reason: str | None = None
