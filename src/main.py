"""Main orchestration script for Austin House Hunter."""

import json
import os
import sys
from pathlib import Path

import yaml

from buckets import coarse_bucket_candidate, select_bucketed
from email_sender import EmailSender
from filters import ListingFilter
from learning import load_preferences
from location import distance_to_sapphire, get_neighborhood
from zillow_client import (
    ZillowClient,
    check_has_pool,
    extract_schools,
    parse_listing,
    passes_pool_filter,
)

# Configuration
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

    # Area targeting is driven by the explicit buckets in config now, NOT by
    # learned preferences. We still load the (neutral) prefs to pass through to
    # the email renderer, but we intentionally do not regenerate them from the
    # old favorites — that would re-introduce the stale South-Austin bias.
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

    # Search for listings (with pagination)
    print("Fetching listings from Zillow...")
    raw_listings = []
    try:
        response = zillow.search_by_prompt(search_prompt)
        page1, total_pages = zillow.extract_search_results(response)
        raw_listings.extend(page1)
        print(f"Found {len(page1)} raw listings (page 1 of {total_pages})")

        # Fetch page 2 if available
        if total_pages > 1:
            response_p2 = zillow.search_by_prompt(search_prompt, page=2)
            page2, _ = zillow.extract_search_results(response_p2)
            raw_listings.extend(page2)
            print(f"Found {len(page2)} raw listings (page 2)")
    except Exception as e:
        print(f"Error fetching listings: {e}")
        return 1

    # Do targeted searches for each bucket's configured areas (with pagination).
    search_areas: list[str] = []
    for bucket in config.get("buckets", []):
        for area in bucket.get("search_areas", []):
            if area not in search_areas:
                search_areas.append(area)
    for area in search_areas:
        try:
            area_prompt = zillow.build_search_prompt(config, location_override=area)
            print(f"Targeted search: {area_prompt}")
            nb_response = zillow.search_by_prompt(area_prompt)
            nb_page1, nb_total_pages = zillow.extract_search_results(nb_response)
            raw_listings.extend(nb_page1)
            print(f"  Found {len(nb_page1)} listings in {area} (page 1 of {nb_total_pages})")

            if nb_total_pages > 1:
                nb_response_p2 = zillow.search_by_prompt(area_prompt, page=2)
                nb_page2, _ = zillow.extract_search_results(nb_response_p2)
                raw_listings.extend(nb_page2)
                print(f"  Found {len(nb_page2)} listings in {area} (page 2)")
        except Exception as e:
            print(f"  Targeted search for {area} failed: {e}")

    listings = [parse_listing(r) for r in raw_listings]

    # Deduplicate by zpid
    seen_zpids = set()
    unique_listings = []
    for listing in listings:
        zpid = listing.get("zpid")
        if zpid and zpid not in seen_zpids:
            seen_zpids.add(zpid)
            unique_listings.append(listing)
        elif not zpid:
            unique_listings.append(listing)
    listings = unique_listings
    print(f"After deduplication: {len(listings)} listings")

    # Apply initial filters (price, beds, baths, sqft, type)
    listing_filter = ListingFilter(config)
    filtered = listing_filter.filter_listings(listings)
    print(f"After initial filtering: {len(filtered)} listings match criteria")

    # Enrich with distance calculations (needed for all filtered, including favorites)
    for listing in filtered:
        enrich_listing(listing)

    # Remove already-seen listings BEFORE expensive property detail API calls
    favorite_zpids = set(favorites.keys())
    if TESTING_MODE:
        candidates = [
            l for l in filtered
            if l.get("zpid") and l["zpid"] not in favorite_zpids
        ]
        print(f"After removing favorites only (testing mode): {len(candidates)} candidates")
    else:
        dismissed_zpids = set(dismissed)
        candidates = [
            l for l in filtered
            if l.get("zpid") and l["zpid"] not in favorite_zpids and l["zpid"] not in dismissed_zpids
        ]
        print(f"After removing favorites/dismissed: {len(candidates)} candidates")

    # Geographic pre-filter: only spend (paid) property-detail lookups on homes
    # that could plausibly land in a bucket. Drops far-flung homes (south/east
    # Austin, far suburbs) before the expensive per-listing detail fetch.
    buckets = config.get("buckets", [])
    if buckets:
        before = len(candidates)
        candidates = [l for l in candidates if coarse_bucket_candidate(l, buckets)]
        print(f"After geo pre-filter: {len(candidates)} candidates "
              f"(dropped {before - len(candidates)} out-of-area)")

    # Fetch property details for pool + school data. Pools are a strict
    # dealbreaker, so fail CLOSED: when 'pool' is excluded, only listings
    # CONFIRMED pool-free survive — unknown or failed lookups are dropped. The
    # zoned high school is extracted from the SAME call (zero extra API calls).
    exclude_pool = "pool" in config.get("exclude_features", [])
    print(f"Fetching property details for {len(candidates)} candidates (pool + school)...")
    new_listings = []
    pool_excluded = 0
    pool_unknown_excluded = 0
    for listing in candidates:
        addr = listing.get("address", "Unknown")
        zpid = listing.get("zpid")
        details = zillow.get_property_details(zpid) if zpid else None

        if details:
            schools = extract_schools(details)
            listing["high_school"] = schools.get("high_school")
            listing["schools"] = schools.get("schools", [])
            if exclude_pool:
                has_pool, pool_reason = check_has_pool(details)
            else:
                has_pool, pool_reason = None, "pool filter off"
        else:
            # No zpid or the detail fetch failed — we cannot confirm pool-free.
            has_pool = None
            pool_reason = "no zpid" if not zpid else "detail fetch failed"
        listing["has_pool"] = has_pool

        # Fail closed: only confirmed pool-free listings survive when excluding pools.
        if not passes_pool_filter(has_pool, exclude_pool):
            if has_pool is True:
                pool_excluded += 1
                print(f"  EXCLUDED (pool):         {addr} — {pool_reason}")
            else:
                pool_unknown_excluded += 1
                print(f"  EXCLUDED (pool unknown): {addr} — {pool_reason}")
            continue

        if exclude_pool:
            hs = listing.get("high_school")
            print(f"  OK (no pool): {addr}" + (f" — zoned {hs}" if hs else ""))
        new_listings.append(listing)

    if exclude_pool:
        print(f"After pool/school step: {len(new_listings)} kept "
              f"(excluded {pool_excluded} confirmed pools, "
              f"{pool_unknown_excluded} unknown/unconfirmed)")

    # Bucket selection: fill each bucket up to its count, ranked cheaper+newer.
    # Short buckets widen to relax_neighborhoods, then send fewer (no cross-fill).
    min_price = config.get("min_price")
    if buckets:
        top_listings = select_bucketed(new_listings, buckets, min_price)
        for bucket in buckets:
            name = bucket.get("name", "")
            chosen = [l for l in top_listings if l.get("bucket") == name]
            want = bucket.get("count", 0)
            short = want - len(chosen)
            print(f"  Bucket '{name}': {len(chosen)}/{want}"
                  + (f" (SHORT by {short})" if short > 0 else ""))
    else:
        # Fallback (config without buckets): cheapest-first up to listings_per_email.
        limit = config.get("listings_per_email", 10)
        top_listings = sorted(new_listings, key=lambda x: x.get("price") or 0)[:limit]

    print(f"Selected {len(top_listings)} listing(s) across {len(buckets)} bucket(s)")
    for i, l in enumerate(top_listings):
        print(f"  {i+1}. [{l.get('bucket', '—')}] {l.get('address', 'Unknown')} "
              f"(${(l.get('price') or 0):,.0f}, HS: {l.get('high_school') or 'n/a'}, "
              f"nbhd: {l.get('neighborhood', 'Unknown')})")

    # Save these as pending (only matters if not in testing mode)
    if not TESTING_MODE:
        new_pending = [l["zpid"] for l in top_listings if l.get("zpid")]
        save_pending(new_pending)

    # Prepare favorites list for email (enrich with current data if available)
    favorites_list = []
    favorites_updated = False
    for zpid, fav_data in favorites.items():
        # Try to find fresh data in current search results first
        fresh = next((l for l in filtered if l.get("zpid") == zpid), None)
        if fresh:
            enrich_listing(fresh)
            # Persist enriched data back so future runs don't need to re-fetch
            favorites[zpid] = fresh
            favorites_updated = True
            favorites_list.append(fresh)
        elif fav_data.get("price") and fav_data.get("address"):
            # Have real data stored already — just enrich and use it
            enrich_listing(fav_data)
            favorites_list.append(fav_data)
        else:
            # Stub from workflow (only zpid/zillow_url) — fetch from API
            print(f"Fetching details for favorite stub: zpid={zpid}")
            details = zillow.get_property_details(zpid)
            if details:
                parsed = parse_listing(details)
                parsed["zpid"] = zpid  # ensure zpid is set
                enrich_listing(parsed)
                # Save enriched data so we don't re-fetch next time
                favorites[zpid] = parsed
                favorites_updated = True
                favorites_list.append(parsed)
                print(f"  Enriched favorite: {parsed.get('address', 'Unknown')}")
            else:
                # API failed — use stub but at least enrich what we have
                print(f"  Could not fetch details for favorite zpid={zpid}, using stub")
                enrich_listing(fav_data)
                favorites_list.append(fav_data)

    if favorites_updated:
        save_favorites(favorites)

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
