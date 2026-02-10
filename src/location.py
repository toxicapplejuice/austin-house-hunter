"""Location utilities for neighborhood and direction detection."""

import math

# Downtown Austin center (Congress & 6th)
DOWNTOWN_LAT = 30.2672
DOWNTOWN_LON = -97.7431

# Sapphire coordinates (assuming downtown Austin area - update if different)
SAPPHIRE_LAT = 30.2672
SAPPHIRE_LON = -97.7431

# Austin neighborhood approximate boundaries (simplified)
NEIGHBORHOODS = {
    # Central
    "Downtown": {"lat_min": 30.26, "lat_max": 30.28, "lon_min": -97.76, "lon_max": -97.73},
    "East Austin": {"lat_min": 30.25, "lat_max": 30.30, "lon_min": -97.73, "lon_max": -97.68},
    "Hyde Park": {"lat_min": 30.30, "lat_max": 30.32, "lon_min": -97.74, "lon_max": -97.71},
    "Travis Heights": {"lat_min": 30.24, "lat_max": 30.26, "lon_min": -97.75, "lon_max": -97.73},
    "South Congress": {"lat_min": 30.23, "lat_max": 30.26, "lon_min": -97.76, "lon_max": -97.74},
    "Zilker": {"lat_min": 30.26, "lat_max": 30.28, "lon_min": -97.78, "lon_max": -97.76},
    "Tarrytown": {"lat_min": 30.29, "lat_max": 30.32, "lon_min": -97.78, "lon_max": -97.75},
    "Clarksville": {"lat_min": 30.28, "lat_max": 30.30, "lon_min": -97.76, "lon_max": -97.74},
    "Mueller": {"lat_min": 30.29, "lat_max": 30.32, "lon_min": -97.71, "lon_max": -97.68},
    "Crestview": {"lat_min": 30.32, "lat_max": 30.35, "lon_min": -97.74, "lon_max": -97.71},
    "Allandale": {"lat_min": 30.32, "lat_max": 30.35, "lon_min": -97.76, "lon_max": -97.73},
    "Brentwood": {"lat_min": 30.32, "lat_max": 30.34, "lon_min": -97.73, "lon_max": -97.71},
    "Rosedale": {"lat_min": 30.30, "lat_max": 30.32, "lon_min": -97.76, "lon_max": -97.73},
    "North Loop": {"lat_min": 30.31, "lat_max": 30.33, "lon_min": -97.72, "lon_max": -97.70},
    "Windsor Park": {"lat_min": 30.30, "lat_max": 30.33, "lon_min": -97.70, "lon_max": -97.67},
    "South Lamar": {"lat_min": 30.23, "lat_max": 30.26, "lon_min": -97.80, "lon_max": -97.76},
    "Barton Hills": {"lat_min": 30.24, "lat_max": 30.27, "lon_min": -97.80, "lon_max": -97.77},
    "West Lake Hills": {"lat_min": 30.28, "lat_max": 30.32, "lon_min": -97.82, "lon_max": -97.78},
    "Circle C": {"lat_min": 30.16, "lat_max": 30.20, "lon_min": -97.88, "lon_max": -97.83},
    "Pflugerville": {"lat_min": 30.42, "lat_max": 30.48, "lon_min": -97.65, "lon_max": -97.58},
    "Round Rock": {"lat_min": 30.48, "lat_max": 30.55, "lon_min": -97.72, "lon_max": -97.65},
    "Cedar Park": {"lat_min": 30.48, "lat_max": 30.54, "lon_min": -97.85, "lon_max": -97.78},
    "Lakeway": {"lat_min": 30.34, "lat_max": 30.38, "lon_min": -97.98, "lon_max": -97.92},
    "Bee Cave": {"lat_min": 30.30, "lat_max": 30.34, "lon_min": -97.98, "lon_max": -97.92},
    "Manor": {"lat_min": 30.34, "lat_max": 30.38, "lon_min": -97.58, "lon_max": -97.52},
    "Kyle": {"lat_min": 29.98, "lat_max": 30.04, "lon_min": -97.90, "lon_max": -97.84},
    "Buda": {"lat_min": 30.06, "lat_max": 30.10, "lon_min": -97.86, "lon_max": -97.80},
}


def get_direction_from_downtown(lat: float, lon: float) -> str:
    """
    Get cardinal/intercardinal direction from downtown Austin.

    Returns: N, S, E, W, NE, NW, SE, SW
    """
    lat_diff = lat - DOWNTOWN_LAT
    lon_diff = lon - DOWNTOWN_LON

    # Determine primary direction
    if abs(lat_diff) < 0.01 and abs(lon_diff) < 0.01:
        return "Central"

    directions = []

    if lat_diff > 0.02:
        directions.append("North")
    elif lat_diff < -0.02:
        directions.append("South")

    if lon_diff > 0.02:
        directions.append("East")
    elif lon_diff < -0.02:
        directions.append("West")

    if not directions:
        # Very close to downtown
        if lat_diff > 0:
            return "North"
        elif lat_diff < 0:
            return "South"
        elif lon_diff > 0:
            return "East"
        else:
            return "West"

    return " ".join(directions)


def get_neighborhood(lat: float, lon: float) -> tuple[str, str]:
    """
    Get the neighborhood name and direction for coordinates.

    Returns: (neighborhood_name, direction)
    """
    direction = get_direction_from_downtown(lat, lon)

    # Check if coordinates fall within a known neighborhood
    for name, bounds in NEIGHBORHOODS.items():
        if (bounds["lat_min"] <= lat <= bounds["lat_max"] and
            bounds["lon_min"] <= lon <= bounds["lon_max"]):
            return name, direction

    # If no exact match, return general area based on direction
    if "North" in direction:
        if "East" in direction:
            return "North Austin", direction
        elif "West" in direction:
            return "Northwest Austin", direction
        else:
            return "North Austin", direction
    elif "South" in direction:
        if "East" in direction:
            return "Southeast Austin", direction
        elif "West" in direction:
            return "Southwest Austin", direction
        else:
            return "South Austin", direction
    elif "East" in direction:
        return "East Austin", direction
    elif "West" in direction:
        return "West Austin", direction
    else:
        return "Central Austin", direction


def distance_to_sapphire(lat: float, lon: float) -> float:
    """
    Calculate distance from a point to Sapphire.

    Args:
        lat: Latitude of the property
        lon: Longitude of the property

    Returns:
        Distance in miles
    """
    # Earth's radius in miles
    R = 3959

    # Convert to radians
    lat1_rad = math.radians(lat)
    lat2_rad = math.radians(SAPPHIRE_LAT)
    delta_lat = math.radians(SAPPHIRE_LAT - lat)
    delta_lon = math.radians(SAPPHIRE_LON - lon)

    # Haversine formula
    a = (
        math.sin(delta_lat / 2) ** 2
        + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(delta_lon / 2) ** 2
    )
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    return R * c
