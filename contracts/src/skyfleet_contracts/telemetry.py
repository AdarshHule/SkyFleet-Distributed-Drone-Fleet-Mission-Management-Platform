from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class DroneStatus(StrEnum):
    IDLE = "IDLE"
    FLYING = "FLYING"
    RETURNING = "RETURNING"
    LANDED = "LANDED"
    CHARGING = "CHARGING"


class TelemetryV1(BaseModel):
    model_config = ConfigDict(extra="ignore")

    drone_id: str = Field(pattern=r"^SF-[A-Z]{2}-\d{3}$")
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    altitude_m: float = Field(ge=0)
    speed_mps: float = Field(ge=0)
    battery_pct: int = Field(ge=0, le=100)
    gps_satellites: int = Field(ge=0)
    heading_deg: float = Field(ge=0, lt=360)
    status: DroneStatus
