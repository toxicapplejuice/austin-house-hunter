"""Location utilities for neighborhood and direction detection."""

import math

# Downtown Austin center (Congress & 6th)
DOWNTOWN_LAT = 30.2672
DOWNTOWN_LON = -97.7431

# Sapphire coordinates (assuming downtown Austin area - update if different)
SAPPHIRE_LAT = 30.2672
SAPPHIRE_LON = -97.7431

# Austin neighborhood centers (lat, lon) for proximity matching
NEIGHBORHOODS = {
    # Central Austin
    "Downtown": (30.2672, -97.7431),
    "East Austin": (30.2650, -97.7150),
    "East Cesar Chavez": (30.2580, -97.7200),
    "Holly": (30.2550, -97.7180),
    "Rainey Street": (30.2590, -97.7390),
    "South Congress (SoCo)": (30.2480, -97.7490),
    "Travis Heights": (30.2450, -97.7420),
    "Zilker": (30.2670, -97.7730),
    "Barton Hills": (30.2550, -97.7850),
    "Bouldin Creek": (30.2450, -97.7580),
    "Clarksville": (30.2850, -97.7550),
    "Old West Austin": (30.2780, -97.7620),
    "Tarrytown": (30.3050, -97.7700),
    "Pemberton Heights": (30.2950, -97.7580),

    # North Central
    "Hyde Park": (30.3050, -97.7280),
    "North Loop": (30.3180, -97.7150),
    "Rosedale": (30.3100, -97.7450),
    "Allandale": (30.3350, -97.7420),
    "Crestview": (30.3380, -97.7250),
    "Brentwood": (30.3280, -97.7180),
    "Highland": (30.3100, -97.7080),
    "Windsor Park": (30.3150, -97.6900),
    "Mueller": (30.2980, -97.7020),
    "University of Texas": (30.2850, -97.7350),

    # Far North
    "North Austin": (30.3800, -97.7200),
    "North Burnet": (30.3650, -97.7180),
    "Domain": (30.4020, -97.7250),
    "Arboretum": (30.3950, -97.7480),
    "Great Hills": (30.4100, -97.7580),
    "Balcones Woods": (30.4050, -97.7680),

    # Northwest
    "Northwest Hills": (30.3650, -97.7650),
    "Far West": (30.3580, -97.7580),
    "Cat Mountain": (30.3450, -97.7850),
    "Jester": (30.3750, -97.7850),

    # East
    "Govalle": (30.2650, -97.7020),
    "Johnston Terrace": (30.2700, -97.6950),
    "MLK": (30.2780, -97.7080),
    "Cherrywood": (30.2920, -97.7120),
    "French Place": (30.2950, -97.7180),
    "Manor Road": (30.2880, -97.7050),

    # South
    "South Austin": (30.2150, -97.7700),
    "South Lamar": (30.2350, -97.7850),
    "Galindo": (30.2350, -97.7650),
    "St. Edwards": (30.2280, -97.7550),
    "Dawson": (30.2380, -97.7620),

    # Far South
    "Circle C": (30.1750, -97.8550),
    "Slaughter Lane": (30.1680, -97.8250),
    "Manchaca": (30.1450, -97.8350),
    "Oak Hill": (30.2350, -97.8650),

    # West
    "West Lake Hills": (30.2980, -97.8050),
    "Rollingwood": (30.2750, -97.7950),
    "Bee Cave": (30.3150, -97.9450),
    "Lakeway": (30.3580, -97.9850),

    # Suburbs
    "Pflugerville": (30.4450, -97.6200),
    "Round Rock": (30.5080, -97.6850),
    "Cedar Park": (30.5050, -97.8200),
    "Leander": (30.5780, -97.8550),
    "Georgetown": (30.6330, -97.6770),
    "Kyle": (29.9890, -97.8770),
    "Buda": (30.0850, -97.8400),
    "Manor": (30.3420, -97.5570),
    "Bastrop": (30.1100, -97.3150),
}


def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate distance between two points in miles."""
    R = 3959  # Earth's radius in miles

    lat1_rad = math.radians(lat1)
    lat2_rad = math.radians(lat2)
    delta_lat = math.radians(lat2 - lat1)
    delta_lon = math.radians(lon2 - lon1)

    a = (
        math.sin(delta_lat / 2) ** 2
        + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(delta_lon / 2) ** 2
    )
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    return R * c


def get_direction_from_downtown(lat: float, lon: float) -> str:
    """Get cardinal direction from downtown Austin."""
    lat_diff = lat - DOWNTOWN_LAT
    lon_diff = lon - DOWNTOWN_LON

    # Very close to downtown
    if abs(lat_diff) < 0.015 and abs(lon_diff) < 0.015:
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
        if abs(lat_diff) > abs(lon_diff):
            return "North" if lat_diff > 0 else "South"
        else:
            return "East" if lon_diff > 0 else "West"

    return " ".join(directions)


def get_neighborhood(lat: float, lon: float) -> tuple[str, str]:
    """
    Get the closest neighborhood name and direction for coordinates.

    Returns: (neighborhood_name, direction)
    """
    direction = get_direction_from_downtown(lat, lon)

    # Find the closest neighborhood by distance
    closest_name = None
    closest_distance = float("inf")

    for name, (n_lat, n_lon) in NEIGHBORHOODS.items():
        dist = haversine_distance(lat, lon, n_lat, n_lon)
        if dist < closest_distance:
            closest_distance = dist
            closest_name = name

    # If the closest neighborhood is more than 5 miles away, it's probably
    # in an area we don't have mapped well - use generic direction
    if closest_distance > 5:
        if "North" in direction:
            closest_name = "North Austin"
        elif "South" in direction:
            closest_name = "South Austin"
        elif "East" in direction:
            closest_name = "East Austin"
        elif "West" in direction:
            closest_name = "West Austin"
        else:
            closest_name = "Central Austin"

    return closest_name, direction


def distance_to_sapphire(lat: float, lon: float) -> float:
    """Calculate distance from a point to Sapphire in miles."""
    return haversine_distance(lat, lon, SAPPHIRE_LAT, SAPPHIRE_LON)


def get_nearby_neighborhoods(lat: float, lon: float, radius_miles: float = 3.0) -> list[str]:
    """Get all neighborhoods within a radius of the given coordinates."""
    nearby = []
    for name, (n_lat, n_lon) in NEIGHBORHOODS.items():
        dist = haversine_distance(lat, lon, n_lat, n_lon)
        if dist <= radius_miles:
            nearby.append(name)
    return nearby
