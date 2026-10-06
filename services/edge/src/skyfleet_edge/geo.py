import math

METERS_PER_DEG_LAT = 111_320.0


def distance_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Approximate distance in metres. Accurate enough for a few km."""
    dlat = (lat2 - lat1) * METERS_PER_DEG_LAT
    dlon = (
        (lon2 - lon1) * METERS_PER_DEG_LAT * math.cos(math.radians((lat1 + lat2) / 2))
    )
    return math.hypot(dlat, dlon)


def heading_deg(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Compass heading from point 1 to point 2: 0 = north, 90 = east."""
    dlat = lat2 - lat1
    dlon = (lon2 - lon1) * math.cos(math.radians((lat1 + lat2) / 2))
    h = math.degrees(math.atan2(dlon, dlat)) % 360
    return 0.0 if h >= 360 else h  # float rounding can produce exactly 360.0


def move_towards(
    lat: float, lon: float, target_lat: float, target_lon: float, step_m: float
) -> tuple[float, float]:
    """Move up to step_m metres towards the target. Never overshoot."""
    dist = distance_m(lat, lon, target_lat, target_lon)
    if dist <= step_m:
        return target_lat, target_lon
    f = step_m / dist
    return lat + (target_lat - lat) * f, lon + (target_lon - lon) * f
