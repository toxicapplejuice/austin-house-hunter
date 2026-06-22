"""One-off helper to confirm where the Zillow/RapidAPI property endpoint exposes
the assigned high school (and pool data), so extract_schools() targets the right
fields.

Usage:
    RAPIDAPI_KEY=... python scripts/inspect_property.py <zpid>

Pick a zpid you expect to be Westwood-zoned (a Round Rock / NW Austin listing).
Prints the raw school-ish blobs plus what check_has_pool / extract_schools
currently derive. If the assigned high school shows up under a field this script
doesn't print, add it and update extract_schools().
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from zillow_client import ZillowClient, check_has_pool, extract_schools  # noqa: E402


def main() -> int:
    if len(sys.argv) < 2:
        print("usage: RAPIDAPI_KEY=... python scripts/inspect_property.py <zpid>")
        return 1

    zpid = sys.argv[1]
    details = ZillowClient().get_property_details(zpid)
    if not details:
        print("No details returned (check RAPIDAPI_KEY and zpid).")
        return 1

    prop = details.get("property", details)
    reso = prop.get("resoFacts") or {}

    print("=== top-level property keys ===")
    print(sorted(prop.keys()))

    print("\n=== candidate school fields ===")
    for source, blob in (("property", prop), ("resoFacts", reso)):
        for key in (
            "schools", "schoolDistrict", "highSchool", "highSchoolDistrict",
            "middleOrJuniorSchool", "elementarySchool",
        ):
            if key in blob:
                print(f"{source}[{key}] = {json.dumps(blob[key], indent=2)[:1500]}")

    print("\n=== derived ===")
    print("check_has_pool ->", check_has_pool(details))
    print("extract_schools ->", json.dumps(extract_schools(details), indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
