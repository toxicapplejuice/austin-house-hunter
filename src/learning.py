"""Learning module to adapt preferences based on favorited houses."""

import json
from pathlib import Path
from typing import Any

from location import get_nearby_neighborhoods

DATA_DIR = Path(__file__).parent.parent / "data"


def load_preferences() -> dict[str, Any]:
    """Load learned preferences from file."""
    prefs_file = DATA_DIR / "preferences.json"
    if prefs_file.exists():
        with open(prefs_file) as f:
            return json.load(f)
    return get_default_preferences()


def save_preferences(prefs: dict[str, Any]) -> None:
    """Save learned preferences to file."""
    DATA_DIR.mkdir(exist_ok=True)
    prefs_file = DATA_DIR / "preferences.json"
    with open(prefs_file, "w") as f:
        json.dump(prefs, f, indent=2)


def get_default_preferences() -> dict[str, Any]:
    """Return default preferences structure."""
    return {
        "preferred_neighborhoods": [],
        "neighborhood_weights": {},
        "ideal_price": None,
        "ideal_sqft": None,
        "ideal_beds": None,
        "ideal_baths": None,
        "hoa_preference": None,  # None = no preference, True = prefer HOA, False = prefer no HOA
        "price_history": [],
        "sqft_history": [],
        "beds_history": [],
        "baths_history": [],
    }


def analyze_favorite(listing: dict[str, Any]) -> dict[str, Any]:
    """Extract learnable features from a favorited listing."""
    features = {
        "neighborhood": listing.get("neighborhood"),
        "price": listing.get("price"),
        "sqft": listing.get("sqft"),
        "beds": listing.get("beds"),
        "baths": listing.get("baths"),
        "has_hoa": listing.get("has_hoa"),
        "latitude": listing.get("latitude"),
        "longitude": listing.get("longitude"),
    }
    return features


def update_preferences_from_favorites(favorites: dict[str, dict]) -> dict[str, Any]:
    """
    Analyze all favorites and update preferences.

    This recalculates preferences from scratch based on all favorited listings.
    """
    prefs = get_default_preferences()

    if not favorites:
        return prefs

    # Collect data from all favorites
    neighborhoods = []
    prices = []
    sqfts = []
    beds_list = []
    baths_list = []
    hoa_values = []

    for zpid, listing in favorites.items():
        if listing.get("neighborhood"):
            neighborhoods.append(listing["neighborhood"])

            # Also add nearby neighborhoods with lower weight
            lat = listing.get("latitude")
            lon = listing.get("longitude")
            if lat and lon:
                nearby = get_nearby_neighborhoods(lat, lon, radius_miles=2.0)
                neighborhoods.extend(nearby)

        if listing.get("price"):
            prices.append(listing["price"])

        if listing.get("sqft"):
            sqfts.append(listing["sqft"])

        if listing.get("beds"):
            beds_list.append(listing["beds"])

        if listing.get("baths"):
            baths_list.append(listing["baths"])

        if listing.get("has_hoa") is not None:
            hoa_values.append(listing["has_hoa"])

    # Calculate neighborhood weights
    neighborhood_counts = {}
    for n in neighborhoods:
        neighborhood_counts[n] = neighborhood_counts.get(n, 0) + 1

    # Normalize to weights (1.0 = baseline, higher = more preferred)
    if neighborhood_counts:
        max_count = max(neighborhood_counts.values())
        prefs["neighborhood_weights"] = {
            n: 1.0 + (count / max_count) * 0.5  # Weight range: 1.0 to 1.5
            for n, count in neighborhood_counts.items()
        }
        # Top neighborhoods
        sorted_neighborhoods = sorted(neighborhood_counts.items(), key=lambda x: -x[1])
        prefs["preferred_neighborhoods"] = [n for n, _ in sorted_neighborhoods[:5]]

    # Calculate ideal values (weighted average favoring recent)
    if prices:
        prefs["ideal_price"] = sum(prices) / len(prices)
        prefs["price_history"] = prices[-10:]  # Keep last 10

    if sqfts:
        prefs["ideal_sqft"] = sum(sqfts) / len(sqfts)
        prefs["sqft_history"] = sqfts[-10:]

    if beds_list:
        prefs["ideal_beds"] = sum(beds_list) / len(beds_list)
        prefs["beds_history"] = beds_list[-10:]

    if baths_list:
        prefs["ideal_baths"] = sum(baths_list) / len(baths_list)
        prefs["baths_history"] = baths_list[-10:]

    # HOA preference (if consistent pattern)
    if hoa_values:
        hoa_true = sum(1 for v in hoa_values if v)
        hoa_false = len(hoa_values) - hoa_true
        if hoa_true > hoa_false * 2:
            prefs["hoa_preference"] = True
        elif hoa_false > hoa_true * 2:
            prefs["hoa_preference"] = False
        # Otherwise, no clear preference

    return prefs


def calculate_preference_boost(listing: dict[str, Any], prefs: dict[str, Any]) -> float:
    """
    Calculate a score boost/penalty based on learned preferences.

    Returns a multiplier: 1.0 = neutral, >1.0 = boost, <1.0 = penalty
    """
    if not prefs:
        return 1.0

    boost = 1.0

    # Neighborhood boost
    neighborhood = listing.get("neighborhood")
    if neighborhood and prefs.get("neighborhood_weights"):
        weight = prefs["neighborhood_weights"].get(neighborhood, 1.0)
        boost *= weight

    # Price proximity boost (closer to ideal = better)
    price = listing.get("price")
    ideal_price = prefs.get("ideal_price")
    if price and ideal_price:
        # Calculate how close to ideal (within 20% = full boost)
        price_diff_pct = abs(price - ideal_price) / ideal_price
        if price_diff_pct < 0.1:
            boost *= 1.2  # Very close to ideal
        elif price_diff_pct < 0.2:
            boost *= 1.1  # Close to ideal
        elif price_diff_pct > 0.5:
            boost *= 0.9  # Far from ideal

    # Size proximity boost
    sqft = listing.get("sqft")
    ideal_sqft = prefs.get("ideal_sqft")
    if sqft and ideal_sqft:
        sqft_diff_pct = abs(sqft - ideal_sqft) / ideal_sqft
        if sqft_diff_pct < 0.15:
            boost *= 1.1

    # Beds/baths proximity
    beds = listing.get("beds")
    ideal_beds = prefs.get("ideal_beds")
    if beds and ideal_beds:
        if abs(beds - ideal_beds) <= 0.5:
            boost *= 1.05

    baths = listing.get("baths")
    ideal_baths = prefs.get("ideal_baths")
    if baths and ideal_baths:
        if abs(baths - ideal_baths) <= 0.5:
            boost *= 1.05

    # HOA preference
    has_hoa = listing.get("has_hoa")
    hoa_pref = prefs.get("hoa_preference")
    if has_hoa is not None and hoa_pref is not None:
        if has_hoa == hoa_pref:
            boost *= 1.1
        else:
            boost *= 0.9

    return boost


def parse_feedback(feedback_text: str) -> dict[str, Any]:
    """
    Parse natural language feedback into actionable updates.

    Returns a dict with updates to apply.
    """
    feedback_text = feedback_text.lower()
    updates = {}

    # Neighborhood preferences (canonical name -> variants to match)
    neighborhood_variants = {
        "tarrytown": ["tarrytown", "tarry town"],
        "mueller": ["mueller"],
        "hyde park": ["hyde park"],
        "east austin": ["east austin"],
        "south congress": ["south congress"],
        "zilker": ["zilker"],
        "barton hills": ["barton hills"],
        "travis heights": ["travis heights"],
        "clarksville": ["clarksville"],
        "rosedale": ["rosedale"],
        "crestview": ["crestview"],
        "allandale": ["allandale"],
        "downtown": ["downtown"],
        "domain": ["domain"],
        "pflugerville": ["pflugerville"],
        "round rock": ["round rock"],
        "cedar park": ["cedar park"],
        "buda": ["buda"],
        "kyle": ["kyle"],
    }

    for neighborhood, variants in neighborhood_variants.items():
        if any(v in feedback_text for v in variants):
            if "more" in feedback_text or "like" in feedback_text or "prefer" in feedback_text:
                if "add_neighborhoods" not in updates:
                    updates["add_neighborhoods"] = []
                updates["add_neighborhoods"].append(neighborhood.title())
            elif "less" in feedback_text or "avoid" in feedback_text or "no " in feedback_text:
                if "remove_neighborhoods" not in updates:
                    updates["remove_neighborhoods"] = []
                updates["remove_neighborhoods"].append(neighborhood.title())

    # Price updates
    import re
    price_match = re.search(r'(?:max|maximum|under|below|up to)\s*(?:price)?\s*\$([\d,.]+)\s*([mk])?', feedback_text)
    if price_match:
        price_str = price_match.group(1).replace(",", "")
        multiplier = 1
        if price_match.group(2):
            if price_match.group(2).lower() == 'm':
                multiplier = 1_000_000
            elif price_match.group(2).lower() == 'k':
                multiplier = 1_000
        updates["max_price"] = int(float(price_str) * multiplier)

    min_price_match = re.search(r'(?:min|minimum|above|over|at least)\s*(?:price)?\s*\$([\d,.]+)\s*([mk])?', feedback_text)
    if min_price_match:
        price_str = min_price_match.group(1).replace(",", "")
        multiplier = 1
        if min_price_match.group(2):
            if min_price_match.group(2).lower() == 'm':
                multiplier = 1_000_000
            elif min_price_match.group(2).lower() == 'k':
                multiplier = 1_000
        updates["min_price"] = int(float(price_str) * multiplier)

    # HOA preference
    if "no hoa" in feedback_text or "without hoa" in feedback_text or "hate hoa" in feedback_text:
        updates["hoa_preference"] = False
    elif "with hoa" in feedback_text or "prefer hoa" in feedback_text or "like hoa" in feedback_text:
        updates["hoa_preference"] = True

    # Bedrooms
    beds_match = re.search(r'(\d+)\+?\s*(?:bed|bedroom|br|bd)', feedback_text)
    if beds_match:
        updates["min_beds"] = int(beds_match.group(1))

    # Bathrooms
    baths_match = re.search(r'(\d+)\+?\s*(?:bath|bathroom|ba)', feedback_text)
    if baths_match:
        updates["min_baths"] = int(baths_match.group(1))

    return updates


def apply_feedback_updates(updates: dict[str, Any]) -> str:
    """
    Apply parsed feedback updates to config and preferences.

    Returns a summary of changes made.
    """
    changes = []

    # Load current preferences
    prefs = load_preferences()

    # Add neighborhoods
    if "add_neighborhoods" in updates:
        for n in updates["add_neighborhoods"]:
            if n not in prefs.get("preferred_neighborhoods", []):
                if "preferred_neighborhoods" not in prefs:
                    prefs["preferred_neighborhoods"] = []
                prefs["preferred_neighborhoods"].append(n)
                # Also boost the weight
                if "neighborhood_weights" not in prefs:
                    prefs["neighborhood_weights"] = {}
                prefs["neighborhood_weights"][n] = 1.5
                changes.append(f"Added {n} to preferred neighborhoods")

    # Remove neighborhoods
    if "remove_neighborhoods" in updates:
        for n in updates["remove_neighborhoods"]:
            if n in prefs.get("preferred_neighborhoods", []):
                prefs["preferred_neighborhoods"].remove(n)
                changes.append(f"Removed {n} from preferred neighborhoods")
            # Also reduce weight
            if n in prefs.get("neighborhood_weights", {}):
                prefs["neighborhood_weights"][n] = 0.5
                changes.append(f"Reduced weight for {n}")

    # HOA preference
    if "hoa_preference" in updates:
        prefs["hoa_preference"] = updates["hoa_preference"]
        pref_str = "with HOA" if updates["hoa_preference"] else "without HOA"
        changes.append(f"Set HOA preference to: {pref_str}")

    # Save preferences
    save_preferences(prefs)

    # Config updates would go to config.yaml - for now just note them
    config_changes = []
    if "max_price" in updates:
        config_changes.append(f"max_price: {updates['max_price']}")
    if "min_price" in updates:
        config_changes.append(f"min_price: {updates['min_price']}")
    if "min_beds" in updates:
        config_changes.append(f"min_beds: {updates['min_beds']}")
    if "min_baths" in updates:
        config_changes.append(f"min_baths: {updates['min_baths']}")

    if config_changes:
        changes.append(f"Config updates needed: {', '.join(config_changes)}")

    return "\n".join(changes) if changes else "No changes detected from feedback"
