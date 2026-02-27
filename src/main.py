"""Main orchestration script for Austin House Hunter."""

import json
import os
import sys
from pathlib import Path

import yaml

from email_sender import EmailSender
from filters import ListingFilter
from learning import (
    calculate_preference_boost,
    load_preferences,
    save_preferences,
    update_preferences_from_favorites,
)
from location import distance_to_sapphire, get_neighborhood
from zillow_client import ZillowClient, parse_listing

# Configuration
MAX_LISTINGS = 5  # Top N listings to show
DATA_DIR = Path(__file__).parent.parent / "data"

# TESTING MODE: Set to True to disable dismissal (keep showing all houses)
TESTING_MODE = False


def load_config() -> dict:
    """Load configuration from config.yaml or environment."""
    config_path = Path(__file__).parent.parent / "config.yaml"

    if config_path.exists():
        with open(config_path) as f:
            return yaml.safe_load(f)

    # Fall back to environment variables for GitHub Actions
    return {
        "location": os.environ.get("SEARCH_LOCATION", "Austin, TX"),
        "min_price": int(os.environ.get("MIN_PRICE", 0)) or None,
        "max_price": int(os.environ.get("MAX_PRICE", 0)) or None,
        "min_beds": int(os.environ.get("MIN_BEDS", 0)) or None,
        "max_beds": int(os.environ.get("MAX_BEDS", 0)) or None,
        "min_baths": int(os.environ.get("MIN_BATHS", 0)) or None,
        "max_baths": int(os.environ.get("MAX_BATHS", 0)) or None,
        "min_sqft": int(os.environ.get("MIN_SQFT", 0)) or None,
        "max_sqft": int(os.environ.get("MAX_SQFT", 0)) or None,
        "property_types": os.environ.get("PROPERTY_TYPES", "").split(",") or [],
        "zip_codes": os.environ.get("ZIP_CODES", "").split(",") or [],
        "max_days_on_market": int(os.environ.get("MAX_DAYS_ON_MARKET", 0)) or None,
    }


def load_json_file(filename: str) -> dict | list:
    """Load a JSON file from data directory."""
    DATA_DIR.mkdir(exist_ok=True)
    filepath = DATA_DIR / filename
    if filepath.exists():
        with open(filepath) as f:
            return json.load(f)
    return {} if filename.endswith("favorites.json") else []


def save_json_file(filename: str, data: dict | list) -> None:
    """Save data to a JSON file in data directory."""
    DATA_DIR.mkdir(exist_ok=True)
    filepath = DATA_DIR / filename
    with open(filepath, "w") as f:
        json.dump(data, f, indent=2)


def load_favorites() -> dict[str, dict]:
    """Load favorited listings. Returns dict of zpid -> listing data."""
    return load_json_file("favorites.json")


def load_dismissed() -> list[str]:
    """Load dismissed zpids."""
    return load_json_file("dismissed.json")


def load_pending() -> list[str]:
    """Load pending zpids (shown but not yet favorited/dismissed)."""
    return load_json_file("pending.json")


def save_favorites(favorites: dict[str, dict]) -> None:
    """Save favorites."""
    save_json_file("favorites.json", favorites)


def save_dismissed(dismissed: list[str]) -> None:
    """Save dismissed list."""
    save_json_file("dismissed.json", dismissed)


def save_pending(pending: list[str]) -> None:
    """Save pending list."""
    save_json_file("pending.json", pending)


def calculate_relevance_score(listing: dict, config: dict, preferences: dict) -> float:
    """
    Calculate a relevance score for ranking listings.

    Score components (higher is better):
    - Distance score (40%): Closer to Sapphire = better
    - Price score (30%): Lower price within range = better
    - Newness score (30%): Fewer days on market = better
    - Preference boost: Multiplier based on learned preferences

    Returns a score from 0 to 100+.
    """
    # Distance score (0-100, closer is better)
    distance = listing.get("distance")
    if distance is not None:
        # Assume max relevant distance is 20 miles
        distance_score = max(0, 100 - (distance / 20) * 100)
    else:
        distance_score = 50  # Default middle score

    # Price score (0-100, lower is better within range)
    price = listing.get("price") or 0
    min_price = config.get("min_price") or 0
    max_price = config.get("max_price") or price * 2
    if max_price > min_price:
        price_score = 100 - ((price - min_price) / (max_price - min_price)) * 100
        price_score = max(0, min(100, price_score))
    else:
        price_score = 50

    # Newness score (0-100, fewer days is better)
    days = listing.get("days_on_market") or 30  # Default to 30 if unknown
    # Assume 60+ days is old
    newness_score = max(0, 100 - (days / 60) * 100)

    # Weighted combination
    base_score = (
        0.4 * distance_score +
        0.3 * price_score +
        0.3 * newness_score
    )

    # Apply preference boost (learned from favorites)
    preference_boost = calculate_preference_boost(listing, preferences)
    total_score = base_score * preference_boost

    return total_score


def enrich_listing(listing: dict) -> dict:
    """Add calculated fields to a listing."""
    lat = listing.get("latitude")
    lon = listing.get("longitude")

    # Calculate distance to Sapphire
    if lat and lon:
        listing["distance"] = distance_to_sapphire(lat, lon)
        # Get neighborhood and direction
        neighborhood, direction = get_neighborhood(lat, lon)
        listing["neighborhood"] = neighborhood
        listing["direction"] = direction
    else:
        listing["distance"] = None
        listing["neighborhood"] = None
        listing["direction"] = None

    # Use description or address as name
    if listing.get("description"):
        # Truncate long descriptions
        desc = listing["description"]
        if len(desc) > 50:
            listing["name"] = desc[:47] + "..."
        else:
            listing["name"] = desc
    elif not listing.get("name"):
        listing["name"] = listing.get("address") or "Unknown Property"

    return listing


def main() -> int:
    """Run the house hunter."""
    print("Austin House Hunter starting...")
    if TESTING_MODE:
        print("*** TESTING MODE: Dismissal disabled ***")

    # Load configuration
    config = load_config()
    print(f"Searching in: {config.get('location', 'Austin, TX')}")

    # Initialize clients
    try:
        zillow = ZillowClient()
        email_sender = EmailSender()
    except ValueError as e:
        print(f"Configuration error: {e}")
        return 1

    # Support multiple recipients
    recipients = []
    recipient_1 = os.environ.get("RECIPIENT_EMAIL")
    recipient_2 = os.environ.get("RECIPIENT_EMAIL_2")

    if recipient_1:
        recipients.append(recipient_1)
    if recipient_2:
        recipients.append(recipient_2)

    if not recipients:
        print("RECIPIENT_EMAIL environment variable is required")
        return 1

    print(f"Will send to {len(recipients)} recipient(s)")

    # Load existing data
    favorites = load_favorites()
    dismissed = load_dismissed()
    pending = load_pending()

    print(f"Loaded {len(favorites)} favorites, {len(dismissed)} dismissed, {len(pending)} pending")

    # Update learned preferences from favorites
    if favorites:
        print("Updating learned preferences from favorites...")
        preferences = update_preferences_from_favorites(favorites)
        save_preferences(preferences)
        print(f"  Preferred neighborhoods: {preferences.get('preferred_neighborhoods', [])}")
    else:
        preferences = load_preferences()

    # TESTING MODE: Skip dismissal logic
    if not TESTING_MODE:
        # Move pending to dismissed (they weren't favorited since last run)
        if pending:
            print(f"Moving {len(pending)} pending listings to dismissed")
            dismissed.extend(pending)
            save_dismissed(dismissed)
            save_pending([])

    # Build search prompt from config
    search_prompt = zillow.build_search_prompt(config)
    print(f"Search prompt: {search_prompt}")

    # Search for listings
    print("Fetching listings from Zillow...")
    try:
        response = zillow.search_by_prompt(search_prompt)
    except Exception as e:
        print(f"Error fetching listings: {e}")
        return 1

    # Parse listings - handle different response structures
    raw_listings = (
        response.get("results", [])
        or response.get("props", [])
        or response.get("searchResults", [])
        or response.get("data", [])
        or []
    )
    if not raw_listings and isinstance(response, list):
        raw_listings = response
    print(f"Found {len(raw_listings)} raw listings")

    listings = [parse_listing(r) for r in raw_listings]

    # Apply additional filters
    listing_filter = ListingFilter(config)
    filtered = listing_filter.filter_listings(listings)
    print(f"After filtering: {len(filtered)} listings match criteria")

    # Enrich with distance calculations
    for listing in filtered:
        enrich_listing(listing)

    # Filter out favorites (always exclude favorites from new listings)
    favorite_zpids = set(favorites.keys())

    if TESTING_MODE:
        # In testing mode, only exclude favorites, not dismissed
        new_listings = [
            l for l in filtered
            if l.get("zpid") and l["zpid"] not in favorite_zpids
        ]
        print(f"After removing favorites only (testing mode): {len(new_listings)} new listings")
    else:
        # Normal mode: exclude both favorites and dismissed
        dismissed_zpids = set(dismissed)
        new_listings = [
            l for l in filtered
            if l.get("zpid") and l["zpid"] not in favorite_zpids and l["zpid"] not in dismissed_zpids
        ]
        print(f"After removing favorites/dismissed: {len(new_listings)} new listings")

    # Calculate relevance scores (for potential future use)
    for listing in new_listings:
        listing["relevance_score"] = calculate_relevance_score(listing, config, preferences)

    # Split into under/over $1M buckets
    under_1m = [l for l in new_listings if (l.get("price") or 0) < 1_000_000]
    over_1m = [l for l in new_listings if (l.get("price") or 0) >= 1_000_000]

    # Sort each bucket by relevance score descending
    under_1m.sort(key=lambda x: x.get("relevance_score") or 0, reverse=True)
    over_1m.sort(key=lambda x: x.get("relevance_score") or 0, reverse=True)

    # Pick 4 under $1M + 1 over $1M, backfill if a bucket is short
    top_under = under_1m[:4]
    top_over = over_1m[:1]
    top_listings = top_under + top_over
    remaining = MAX_LISTINGS - len(top_listings)
    if remaining > 0:
        extras = [l for l in under_1m[4:] + over_1m[1:] if l not in top_listings]
        top_listings.extend(extras[:remaining])

    # Guarantee at least 1 listing from a preferred neighborhood
    preferred = preferences.get("preferred_neighborhoods", [])
    if preferred:
        has_preferred = any(
            l.get("neighborhood") in preferred for l in top_listings
        )
        if not has_preferred:
            # Find best listing from a preferred neighborhood across all candidates
            preferred_candidates = [
                l for l in new_listings
                if l.get("neighborhood") in preferred and l not in top_listings
            ]
            if preferred_candidates:
                preferred_candidates.sort(key=lambda x: x.get("relevance_score") or 0, reverse=True)
                # Swap out the lowest-scored listing
                top_listings.sort(key=lambda x: x.get("relevance_score") or 0)
                top_listings[0] = preferred_candidates[0]
                print(f"Swapped in preferred neighborhood listing: {preferred_candidates[0].get('neighborhood')}")

    # Sort final list by price descending for display
    top_listings.sort(key=lambda x: x.get("price") or 0, reverse=True)
    print(f"Top {len(top_listings)} listings selected ({len(top_under)} under $1M, {len(top_over)} over $1M)")

    # Log top listings with scores
    for i, l in enumerate(top_listings):
        print(f"  {i+1}. {l.get('address', 'Unknown')} - Score: {l.get('relevance_score', 0):.1f}, "
              f"Neighborhood: {l.get('neighborhood', 'Unknown')}")

    # Save these as pending (only matters if not in testing mode)
    if not TESTING_MODE:
        new_pending = [l["zpid"] for l in top_listings if l.get("zpid")]
        save_pending(new_pending)

    # Prepare favorites list for email (enrich with current data if available)
    favorites_list = []
    for zpid, fav_data in favorites.items():
        # Try to find fresh data for this listing
        fresh = next((l for l in filtered if l.get("zpid") == zpid), None)
        if fresh:
            enrich_listing(fresh)
            favorites_list.append(fresh)
        else:
            # Use stored data, but enrich it
            enrich_listing(fav_data)
            favorites_list.append(fav_data)

    # Sort favorites by distance
    favorites_list.sort(key=lambda x: x.get("distance") or float("inf"))

    # Send email to all recipients
    print(f"Sending email...")
    print(f"  - {len(favorites_list)} favorites")
    print(f"  - {len(top_listings)} new listings")
    print(f"  - {len(recipients)} recipient(s)")

    all_success = True
    for recipient in recipients:
        print(f"  Sending to {recipient}...")
        success = email_sender.send_listings(
            recipient=recipient,
            new_listings=top_listings,
            favorites=favorites_list,
            preferences=preferences,
        )
        if not success:
            all_success = False

    if all_success:
        print("Done!")
        return 0
    else:
        print("Some emails failed to send")
        return 1


if __name__ == "__main__":
    sys.exit(main())
