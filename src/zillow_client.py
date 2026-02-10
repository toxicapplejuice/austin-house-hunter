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
        return response.json()

    def build_search_prompt(self, config: dict[str, Any]) -> str:
        """
        Build a natural language search prompt from config.

        Args:
            config: Configuration dictionary with search criteria

        Returns:
            Natural language prompt string
        """
        parts = []

        # Location
        location = config.get("location", "Austin, TX")

        # Bedrooms
        min_beds = config.get("min_beds")
        max_beds = config.get("max_beds")
        if min_beds and max_beds:
            parts.append(f"{min_beds}-{max_beds} bedroom")
        elif min_beds:
            parts.append(f"{min_beds}+ bedroom")

        # Property type
        property_types = config.get("property_types", [])
        if property_types:
            type_map = {
                "single_family": "single family homes",
                "condo": "condos",
                "townhouse": "townhouses",
                "multi_family": "multi-family homes",
            }
            types_str = " or ".join(type_map.get(t, t) for t in property_types)
            parts.append(types_str)
        else:
            parts.append("homes")

        parts.append("for sale in")
        parts.append(location)

        # Bathrooms
        min_baths = config.get("min_baths")
        if min_baths:
            parts.append(f"with {min_baths}+ bathrooms")

        # Price
        min_price = config.get("min_price")
        max_price = config.get("max_price")
        if min_price and max_price:
            parts.append(f"${min_price:,} to ${max_price:,}")
        elif max_price:
            parts.append(f"under ${max_price:,}")
        elif min_price:
            parts.append(f"over ${min_price:,}")

        # Square footage
        min_sqft = config.get("min_sqft")
        max_sqft = config.get("max_sqft")
        if min_sqft:
            parts.append(f"{min_sqft:,}+ sqft")

        # Days on market
        max_days = config.get("max_days_on_market")
        if max_days:
            parts.append(f"listed in last {max_days} days")

        return " ".join(parts)


def parse_listing(raw: dict[str, Any]) -> dict[str, Any]:
    """Parse a raw listing into a standardized format."""
    # Handle different response formats from the API
    return {
        "zpid": raw.get("zpid"),
        "address": raw.get("streetAddress") or raw.get("address"),
        "city": raw.get("city"),
        "state": raw.get("state"),
        "zipcode": raw.get("zipcode"),
        "price": raw.get("price") or raw.get("unformattedPrice"),
        "beds": raw.get("bedrooms") or raw.get("beds"),
        "baths": raw.get("bathrooms") or raw.get("baths"),
        "sqft": raw.get("livingArea") or raw.get("area"),
        "property_type": raw.get("homeType") or raw.get("propertyType"),
        "days_on_market": raw.get("daysOnZillow") or raw.get("timeOnZillow"),
        "photo_url": raw.get("imgSrc") or raw.get("image"),
        "zillow_url": raw.get("detailUrl") or raw.get("url"),
        "latitude": raw.get("latitude") or raw.get("lat"),
        "longitude": raw.get("longitude") or raw.get("long"),
    }
