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

    def build_search_prompt(self, config: dict[str, Any]) -> str:
        """
        Build a natural language search prompt from config.

        Args:
            config: Configuration dictionary with search criteria

        Returns:
            Natural language prompt string
        """
        # Location
        location = config.get("location", "Austin, TX")

        # Price
        min_price = config.get("min_price")
        max_price = config.get("max_price")

        # Build a simpler, more direct prompt
        # Format: "houses for sale in Austin TX under $1.2M no pool"
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
        "description": description,
        "days_on_market": prop.get("daysOnZillow") or prop.get("timeOnZillow"),
        "photo_url": photo_url or prop.get("imgSrc") or prop.get("image"),
        "zillow_url": zillow_url,
        "latitude": location_obj.get("latitude") or prop.get("latitude") or prop.get("lat"),
        "longitude": location_obj.get("longitude") or prop.get("longitude") or prop.get("long"),
    }
