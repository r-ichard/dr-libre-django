"""Task 22, spec 15.5: the `near` search parameter, `latitude|longitude|distance|unit`."""

import math
from dataclasses import dataclass

MAXIMUM_KILOMETRES = 1000.0
KILOMETRES_PER_MILE = 1.609344
EARTH_RADIUS_KILOMETRES = 6371.0088
UNITS = {"km": 1.0, "[mi_i]": KILOMETRES_PER_MILE}


@dataclass(frozen=True)
class NearPoint:
    latitude: float
    longitude: float
    kilometres: float


def parse_near(text: str) -> NearPoint | None:
    """None when the value is not four parts, a number out of range, or too far to be useful."""
    parts = text.split("|")
    if len(parts) != 4 or parts[3] not in UNITS:
        return None
    try:
        latitude, longitude, distance = (float(part) for part in parts[:3])
    except ValueError:
        return None
    kilometres = distance * UNITS[parts[3]]
    if not (-90 <= latitude <= 90 and -180 <= longitude <= 180):
        return None
    if not 0 <= kilometres <= MAXIMUM_KILOMETRES:
        return None
    return NearPoint(latitude, longitude, kilometres)


def is_within(point: NearPoint, latitude: float, longitude: float) -> bool:
    """Haversine great-circle distance."""
    first, second = math.radians(point.latitude), math.radians(latitude)
    half_latitude = (second - first) / 2
    half_longitude = math.radians(longitude - point.longitude) / 2
    root = (
        math.sin(half_latitude) ** 2
        + math.cos(first) * math.cos(second) * math.sin(half_longitude) ** 2
    )
    distance = 2 * EARTH_RADIUS_KILOMETRES * math.asin(math.sqrt(root))
    return distance <= point.kilometres
