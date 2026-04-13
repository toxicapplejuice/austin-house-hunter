"""Zillow API client using RapidAPI Private-Zillow."""

import os
from typing import Any

import requests


class ZillowClient:
    """Client for Private-Zillow API on RapidAPI."""

    BASE_URL = "https://private-zillow.p.rapidapi.com"

    def __init__(self, api_key: str | None = None):
        self.api_key = api_key or os.environ.get("RAPIDAPI_KEY")
        if not self.api_key:
            raise ValueError("RAPIDAPI_KEY is required")

        self.headers = {
            "x-rapidapi-key": self.api_key,
            "x-rapidapi-host": "private-zillow.p.rapidapi.com",
        }

    def search_by_prompt(
        self,
        prompt: str,
        page: int = 1,
        sort_order: str = "Newest",
    ) -> dict[str, Any]:
        """
        Search for listings using natural language prompt.

        Args:
            prompt: Natural language search like "3 bedroom homes for sale in Austin TX under $500k"
            page: Page number for pagination
            sort_order: Sort order (Newest, Price_High_Low, Price_Low_High, etc.)

        Returns:
            API response with listings
        """
        params = {
            "ai_search_prompt": prompt,
            "page": page,
            "sortOrder": sort_order,
        }

        response = requests.get(
            f"{self.BASE_URL}/search/byaiprompt",
            headers=self.headers,
            params=params,
            timeout=30,
        )
        response.raise_for_status()
        data = response.json()

        # Debug: print response structure
        print(f"API Response keys: {list(data.keys()) if isinstance(data, dict) else 'list'}")
        if isinstance(data, dict):
            for key, value in data.items():
                if isinstance(value, list):
                    print(f"  {key}: list with {len(value)} items")
                elif isinstance(value, dict):
                    print(f"  {key}: dict with keys {list(value.keys())[:5]}")
                else:
                    print(f"  {key}: {type(value).__name__} = {str(value)[:100]}")

        return data

    def get_property_details(self, zpid: str) -> dict[str, Any] | None:
        """
        Fetch detailed property info including pool/feature data.

        Returns parsed property dict or None on failure.
        """
        params = {"zpid": zpid}
        try:
            response = requests.get(
                f"{self.BASE_URL}/property",
                headers=self.headers,
                params=params,
                timeout=30,
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            print(f"  Failed to fetch details for zpid {zpid}: {e}")
            return None

    @staticmethod
    def extract_search_results(response: dict | list) -> tuple[list, int]:
        """Extract listings and total pages from an API search response."""
        if isinstance(response, list):
            return response, 1
        raw_listings = (
            response.get("results", [])
            or response.get("props", [])
            or response.get("searchResults", [])
            or response.get("data", [])
            or []
        )
        pages_info = response.get("pagesInfo", {})
        total_pages = pages_info.get("totalPages", 1) or 1
        return raw_listings, total_pages

    def build_search_prompt(self, config: dict[str, Any], neighborhood: str | None = None) -> str:
        """
        Build a natural language search prompt from config.

        Args:
            config: Configuration dictionary with search criteria
            neighborhood: Optional neighborhood to target the search

        Returns:
            Natural language prompt string
        """
        # Location - use neighborhood if provided
        if neighborhood:
            location = f"{neighborhood}, Austin, TX"
        else:
            location = config.get("location", "Austin, TX")

        # Price
        max_price = config.get("max_price")

        # Build a simpler, more direct prompt
        parts = ["houses for sale in", location]

        if max_price:
            if max_price >= 1_000_000:
                parts.append(f"under ${max_price / 1_000_000:.1f}M")
            else:
                parts.append(f"under ${max_price:,.0f}")

        # Exclude pools
        exclude_features = config.get("exclude_features", [])
        if "pool" in exclude_features:
            parts.append("no pool")

        return " ".join(parts)


def check_has_pool(details: dict[str, Any]) -> tuple[bool | None, str]:
    """
    Check if a property has a pool from property details API response.

    Returns (result, reason) where:
      result: True if pool detected, False if explicitly no pool, None if unknown
      reason: debug string explaining how the result was determined
    """
    prop = details.get("property", details)

    # 1. resoFacts.hasPrivatePool — most reliable structured field
    reso_facts = prop.get("resoFacts") or {}
    has_private_pool = reso_facts.get("hasPrivatePool")
    if has_private_pool is not None:
        return bool(has_private_pool), f"resoFacts.hasPrivatePool={has_private_pool}"

    # 2. resoFacts.poolFeatures — list like ["In Ground", "Gunite"] or ["None"]
    pool_features = reso_facts.get("poolFeatures")
    if pool_features:
        non_none = [f for f in pool_features if f and f.lower() != "none"]
        if non_none:
            return True, f"resoFacts.poolFeatures={non_none}"
        return False, f"resoFacts.poolFeatures=['None']"

    # 3. atAGlanceFacts — list of {factLabel, factValue} dicts
    at_a_glance = prop.get("atAGlanceFacts") or []
    for fact in at_a_glance:
        label = (fact.get("factLabel") or "").lower()
        value = str(fact.get("factValue") or "").lower()
        if "pool" in label or "pool" in value:
            if value in ("false", "no", "none", "") or "no pool" in value:
                return False, f"atAGlanceFacts: {fact.get('factLabel')}={fact.get('factValue')}"
            return True, f"atAGlanceFacts: {fact.get('factLabel')}={fact.get('factValue')}"

    # 4. homeFacts dict
    home_facts = prop.get("homeFacts") or {}
    for key in ("pool", "hasPool", "privatePool"):
        pool_fact = home_facts.get(key)
        if pool_fact is not None:
            if isinstance(pool_fact, bool):
                return pool_fact, f"homeFacts.{key}={pool_fact}"
            val = str(pool_fact).lower()
            if val in ("yes", "true"):
                return True, f"homeFacts.{key}={pool_fact}"
            if val in ("no", "false", "none"):
                return False, f"homeFacts.{key}={pool_fact}"

    # 5. features list (strings or dicts)
    features = prop.get("features") or []
    if isinstance(features, list):
        for feature in features:
            text = feature if isinstance(feature, str) else str(feature)
            text_lower = text.lower()
            if "pool" in text_lower and "no pool" not in text_lower and "pool table" not in text_lower:
                return True, f"features contains: {text[:80]}"

    # 6. amenities list
    amenities = prop.get("amenities") or []
    if isinstance(amenities, list):
        for amenity in amenities:
            text = amenity if isinstance(amenity, str) else str(amenity)
            text_lower = text.lower()
            if "pool" in text_lower and "no pool" not in text_lower:
                return True, f"amenities contains: {text[:80]}"

    # 7. Text fallback: description fields
    description = prop.get("description") or prop.get("homeDescription") or ""
    if description:
        desc_lower = description.lower()
        negatives = ["no pool", "pool table", "carpool", "pool bath"]
        has_pool_keyword = "pool" in desc_lower or "swimming" in desc_lower
        has_negative = any(neg in desc_lower for neg in negatives)
        if has_pool_keyword and not has_negative:
            return True, "description text mentions pool"
        if has_pool_keyword and has_negative:
            return False, "description text mentions pool with negation"

    return None, "no pool data found in any API field"


def parse_listing(raw: dict[str, Any]) -> dict[str, Any]:
    """Parse a raw listing into a standardized format."""
    # Handle nested "property" structure from Private-Zillow API
    prop = raw.get("property", raw)

    # Get nested address
    address_obj = prop.get("address", {})

    # Get nested location
    location_obj = prop.get("location", {})

    # Get price - could be in different places
    price = prop.get("price")
    if isinstance(price, dict):
        price = price.get("value") or price.get("amount")

    # Get media/photos
    media = prop.get("media", {})
    photo_links = media.get("propertyPhotoLinks", {})
    photo_url = photo_links.get("mediumSizeLink") or photo_links.get("highResolutionLink")

    # Build Zillow URL from zpid if not provided
    zpid = prop.get("zpid")
    zillow_url = prop.get("detailUrl") or prop.get("url")
    if not zillow_url and zpid:
        zillow_url = f"https://www.zillow.com/homedetails/{zpid}_zpid/"

    # Get HOA info
    hoa_fee = prop.get("hoaFee") or prop.get("monthlyHoaFee") or prop.get("associationFee")
    has_hoa = hoa_fee is not None and hoa_fee > 0

    # Get stories/levels
    stories = prop.get("stories") or prop.get("levels") or prop.get("numStories")

    # Get description
    description = prop.get("description") or prop.get("homeDescription") or prop.get("listingSubType", {}).get("text")

    # Get home type for display
    home_type = prop.get("homeType") or prop.get("propertyType") or ""

    return {
        "zpid": str(zpid) if zpid else None,
        "address": address_obj.get("streetAddress") or prop.get("streetAddress") or prop.get("address"),
        "city": address_obj.get("city") or prop.get("city"),
        "state": address_obj.get("state") or prop.get("state"),
        "zipcode": address_obj.get("zipcode") or prop.get("zipcode"),
        "price": price,
        "beds": prop.get("bedrooms") or prop.get("beds"),
        "baths": prop.get("bathrooms") or prop.get("baths"),
        "sqft": prop.get("livingArea") or prop.get("area") or prop.get("sqft"),
        "property_type": home_type,
        "stories": stories,
        "has_hoa": has_hoa,
        "hoa_fee": hoa_fee,
        "has_pool": None,  # populated later from property details
        "description": description,
        "days_on_market": prop.get("daysOnZillow") or prop.get("timeOnZillow"),
        "photo_url": photo_url or prop.get("imgSrc") or prop.get("image"),
        "zillow_url": zillow_url,
        "latitude": location_obj.get("latitude") or prop.get("latitude") or prop.get("lat"),
        "longitude": location_obj.get("longitude") or prop.get("longitude") or prop.get("long"),
    }
