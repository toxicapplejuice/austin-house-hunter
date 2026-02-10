"""Distance calculation utilities."""

import math

# Monarch Apartments, Downtown Austin coordinates
MONARCH_LAT = 30.2672
MONARCH_LON = -97.7431


def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Calculate the distance between two points on Earth using the Haversine formula.

    Args:
        lat1, lon1: First point coordinates (degrees)
        lat2, lon2: Second point coordinates (degrees)

    Returns:
        Distance in miles
    """
    # Earth's radius in miles
    R = 3959

    # Convert to radians
    lat1_rad = math.radians(lat1)
    lat2_rad = math.radians(lat2)
    delta_lat = math.radians(lat2 - lat1)
    delta_lon = math.radians(lon2 - lon1)

    # Haversine formula
    a = (
        math.sin(delta_lat / 2) ** 2
        + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(delta_lon / 2) ** 2
    )
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    return R * c


def distance_to_monarch(lat: float, lon: float) -> float:
    """
    Calculate distance from a point to Monarch Apartments downtown.

    Args:
        lat: Latitude of the property
        lon: Longitude of the property

    Returns:
        Distance in miles
    """
    return haversine_distance(lat, lon, MONARCH_LAT, MONARCH_LON)
