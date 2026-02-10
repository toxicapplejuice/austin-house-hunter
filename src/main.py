"""Main orchestration script for Austin House Hunter."""

import json
import os
import sys
from pathlib import Path

import yaml

from email_sender import EmailSender
from filters import ListingFilter
from zillow_client import ZillowClient, parse_listing


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


def load_seen_listings() -> set[str]:
    """Load previously seen listing IDs to avoid duplicates."""
    seen_path = Path(__file__).parent.parent / ".seen_listings.json"
    if seen_path.exists():
        with open(seen_path) as f:
            return set(json.load(f))
    return set()


def save_seen_listings(seen: set[str]) -> None:
    """Save seen listing IDs for next run."""
    seen_path = Path(__file__).parent.parent / ".seen_listings.json"
    with open(seen_path, "w") as f:
        json.dump(list(seen), f)


def main() -> int:
    """Run the house hunter."""
    print("Austin House Hunter starting...")

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

    recipient = os.environ.get("RECIPIENT_EMAIL")
    if not recipient:
        print("RECIPIENT_EMAIL environment variable is required")
        return 1

    # Search for listings
    print("Fetching listings from Zillow...")
    try:
        response = zillow.search_listings(
            location=config.get("location", "Austin, TX"),
            min_price=config.get("min_price"),
            max_price=config.get("max_price"),
            min_beds=config.get("min_beds"),
            max_beds=config.get("max_beds"),
            min_baths=config.get("min_baths"),
            max_baths=config.get("max_baths"),
            min_sqft=config.get("min_sqft"),
            max_sqft=config.get("max_sqft"),
            days_on_zillow=config.get("max_days_on_market"),
        )
    except Exception as e:
        print(f"Error fetching listings: {e}")
        return 1

    # Parse listings
    raw_listings = response.get("results", [])
    print(f"Found {len(raw_listings)} raw listings")

    listings = [parse_listing(r) for r in raw_listings]

    # Apply additional filters
    listing_filter = ListingFilter(config)
    filtered = listing_filter.filter_listings(listings)
    print(f"After filtering: {len(filtered)} listings match criteria")

    # Filter out previously seen listings if configured
    if config.get("only_new_listings", True):
        seen = load_seen_listings()
        new_listings = [l for l in filtered if l.get("zpid") not in seen]
        print(f"New listings (not seen before): {len(new_listings)}")

        # Update seen listings
        for l in filtered:
            if l.get("zpid"):
                seen.add(l["zpid"])
        save_seen_listings(seen)

        filtered = new_listings

    # Sort by price (lowest first)
    filtered.sort(key=lambda x: x.get("price", float("inf")))

    # Send email
    print(f"Sending email to {recipient}...")
    success = email_sender.send_listings(recipient, filtered)

    if success:
        print("Done!")
        return 0
    else:
        print("Failed to send email")
        return 1


if __name__ == "__main__":
    sys.exit(main())
