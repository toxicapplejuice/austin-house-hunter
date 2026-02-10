"""Zillow API client using RapidAPI."""

import os
from typing import Any

import requests


class ZillowClient:
    """Client for Real-Time Zillow Data API on RapidAPI."""

    BASE_URL = "https://real-time-zillow-data.p.rapidapi.com"

    def __init__(self, api_key: str | None = None):
        self.api_key = api_key or os.environ.get("RAPIDAPI_KEY")
        if not self.api_key:
            raise ValueError("RAPIDAPI_KEY is required")

        self.headers = {
            "x-rapidapi-key": self.api_key,
            "x-rapidapi-host": "real-time-zillow-data.p.rapidapi.com",
        }

    def search_listings(
        self,
        location: str,
        status: str = "forSale",
        min_price: int | None = None,
        max_price: int | None = None,
        min_beds: int | None = None,
        max_beds: int | None = None,
        min_baths: int | None = None,
        max_baths: int | None = None,
        min_sqft: int | None = None,
        max_sqft: int | None = None,
        home_type: str | None = None,
        days_on_zillow: int | None = None,
        page: int = 1,
    ) -> dict[str, Any]:
        """
        Search for property listings.

        Args:
            location: City, address, or ZIP code (e.g., "Austin, TX")
            status: "forSale", "forRent", or "sold"
            min_price: Minimum price
            max_price: Maximum price
            min_beds: Minimum bedrooms
            max_beds: Maximum bedrooms
            min_baths: Minimum bathrooms
            max_baths: Maximum bathrooms
            min_sqft: Minimum square footage
            max_sqft: Maximum square footage
            home_type: Property type filter
            days_on_zillow: Max days on market
            page: Page number for pagination

        Returns:
            API response with listings
        """
        params = {
            "location": location,
            "status": status,
            "page": page,
        }

        # Add optional filters
        if min_price:
            params["minPrice"] = min_price
        if max_price:
            params["maxPrice"] = max_price
        if min_beds:
            params["bedsMin"] = min_beds
        if max_beds:
            params["bedsMax"] = max_beds
        if min_baths:
            params["bathsMin"] = min_baths
        if max_baths:
            params["bathsMax"] = max_baths
        if min_sqft:
            params["sqftMin"] = min_sqft
        if max_sqft:
            params["sqftMax"] = max_sqft
        if home_type:
            params["home_type"] = home_type
        if days_on_zillow:
            params["daysOn"] = days_on_zillow

        response = requests.get(
            f"{self.BASE_URL}/search",
            headers=self.headers,
            params=params,
            timeout=30,
        )
        response.raise_for_status()
        return response.json()

    def get_property_details(self, zpid: str) -> dict[str, Any]:
        """
        Get detailed information about a specific property.

        Args:
            zpid: Zillow property ID

        Returns:
            Property details
        """
        response = requests.get(
            f"{self.BASE_URL}/property",
            headers=self.headers,
            params={"zpid": zpid},
            timeout=30,
        )
        response.raise_for_status()
        return response.json()


def parse_listing(raw: dict[str, Any]) -> dict[str, Any]:
    """Parse a raw listing into a standardized format."""
    return {
        "zpid": raw.get("zpid"),
        "address": raw.get("address"),
        "city": raw.get("city"),
        "state": raw.get("state"),
        "zipcode": raw.get("zipcode"),
        "price": raw.get("price"),
        "beds": raw.get("bedrooms"),
        "baths": raw.get("bathrooms"),
        "sqft": raw.get("livingArea"),
        "property_type": raw.get("homeType"),
        "days_on_market": raw.get("daysOnZillow"),
        "photo_url": raw.get("imgSrc"),
        "zillow_url": raw.get("detailUrl"),
        "latitude": raw.get("latitude"),
        "longitude": raw.get("longitude"),
    }
