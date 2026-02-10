"""Filtering logic for house listings."""

from typing import Any


class ListingFilter:
    """Filter listings based on user criteria."""

    def __init__(self, config: dict[str, Any]):
        self.config = config

    def matches(self, listing: dict[str, Any]) -> bool:
        """Check if a listing matches all filter criteria."""
        # Price filter
        price = listing.get("price")
        if price:
            min_price = self.config.get("min_price")
            max_price = self.config.get("max_price")
            if min_price and price < min_price:
                return False
            if max_price and price > max_price:
                return False

        # Bedroom filter
        beds = listing.get("beds")
        if beds:
            min_beds = self.config.get("min_beds")
            max_beds = self.config.get("max_beds")
            if min_beds and beds < min_beds:
                return False
            if max_beds and beds > max_beds:
                return False

        # Bathroom filter
        baths = listing.get("baths")
        if baths:
            min_baths = self.config.get("min_baths")
            max_baths = self.config.get("max_baths")
            if min_baths and baths < min_baths:
                return False
            if max_baths and baths > max_baths:
                return False

        # Square footage filter
        sqft = listing.get("sqft")
        if sqft:
            min_sqft = self.config.get("min_sqft")
            max_sqft = self.config.get("max_sqft")
            if min_sqft and sqft < min_sqft:
                return False
            if max_sqft and sqft > max_sqft:
                return False

        # Property type filter
        property_types = self.config.get("property_types", [])
        if property_types:
            listing_type = (listing.get("property_type") or "").lower()
            # Normalize property type names
            type_mapping = {
                "single_family": ["single_family", "singlefamily", "house", "single", "for_sale"],
                "condo": ["condo", "condominium"],
                "townhouse": ["townhouse", "townhome"],
                "multi_family": ["multi_family", "multifamily", "duplex", "triplex"],
            }
            matched = False
            for config_type in property_types:
                acceptable = type_mapping.get(config_type, [config_type])
                if any(t in listing_type for t in acceptable):
                    matched = True
                    break
            # If no property type info, let it through (don't filter out unknowns)
            if not matched and listing_type:
                return False

        # Zip code filter
        zip_codes = self.config.get("zip_codes", [])
        if zip_codes:
            listing_zip = listing.get("zipcode")
            if listing_zip and str(listing_zip) not in [str(z) for z in zip_codes]:
                return False

        # Days on market filter
        max_days = self.config.get("max_days_on_market")
        if max_days:
            days = listing.get("days_on_market")
            if days and days > max_days:
                return False

        return True

    def filter_listings(self, listings: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Filter a list of listings, returning only those that match criteria."""
        return [listing for listing in listings if self.matches(listing)]
