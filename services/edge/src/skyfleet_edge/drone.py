import math
from dataclasses import dataclass

from skyfleet_contracts import DroneStatus, Envelope, TelemetryV1
from skyfleet_edge import geo

BATTERY_DRAIN_PCT_PER_S = 0.05  # only while flying
ARRIVAL_RADIUS_M = 0.5


@dataclass
class VirtualDrone:
    drone_id: str
    latitude: float
    longitude: float
    altitude_m: float = 0.0
    speed_mps: float = 0.0
    battery_pct: float = 100.0
    heading_deg: float = 0.0
    gps_satellites: int = 14
    status: DroneStatus = DroneStatus.IDLE
    target: tuple[float, float] | None = None
    cruise_speed_mps: float = 10.0
    cruise_altitude_m: float = 80.0

    def fly_to(self, lat: float, lon: float) -> None:
        self.target = (lat, lon)
        self.status = DroneStatus.FLYING

    def step(self, dt: float) -> None:
        """Advance the simulation by dt seconds."""
        if self.status != DroneStatus.FLYING or self.target is None:
            self.speed_mps = 0.0
            return

        target_lat, target_lon = self.target
        self.altitude_m = self.cruise_altitude_m
        self.speed_mps = self.cruise_speed_mps

        self.heading_deg = geo.heading_deg(
            self.latitude,
            self.longitude,
            target_lat,
            target_lon,
        )

        self.latitude, self.longitude = geo.move_towards(
            self.latitude,
            self.longitude,
            target_lat,
            target_lon,
            step_m=self.speed_mps * dt,
        )

        self.battery_pct = max(
            0.0,
            self.battery_pct - BATTERY_DRAIN_PCT_PER_S * dt,
        )

        distance_to_target_m = geo.distance_m(
            self.latitude,
            self.longitude,
            target_lat,
            target_lon,
        )
        if distance_to_target_m < ARRIVAL_RADIUS_M:
            self.status = DroneStatus.LANDED
            self.speed_mps = 0.0
            self.altitude_m = 0.0
            self.target = None


    def to_telemetry(self) -> Envelope[TelemetryV1]:
        telemetry = TelemetryV1(
            drone_id=self.drone_id,
            latitude=self.latitude,
            longitude=self.longitude,
            altitude_m=self.altitude_m,
            speed_mps=self.speed_mps,
            battery_pct=math.floor(self.battery_pct),
            gps_satellites=self.gps_satellites,
            heading_deg=self.heading_deg,
            status=self.status,
        )
        return Envelope[TelemetryV1](
            event_type="drone.telemetry",
            producer="edge-simulator",
            payload=telemetry,
        )