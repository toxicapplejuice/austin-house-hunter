"""One-off API diagnostic (run in CI with the RAPIDAPI_KEY secret).

The /property?zpid=X endpoint 404s, so pool/school data is never retrieved. This
dumps a full search-result item (to see whether pool/school is already present)
and probes candidate property-detail endpoints to find one that returns 200.
Sends NO email. Remove after the detail endpoint is fixed.
"""

import json
import sys
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from zillow_client import ZillowClient  # noqa: E402


def main() -> int:
    client = ZillowClient()
    resp = client.search_by_prompt("houses for sale in Round Rock, TX under $1.2M")
    results, _ = client.extract_search_results(resp)
    if not results:
        print("no search results")
        return 1

    item = results[0]
    print("=== FULL first search result item (all available fields) ===")
    print(json.dumps(item, indent=2)[:8000])

    prop = item.get("property", item)
    zpid = prop.get("zpid") or item.get("zpid")
    detail_url = prop.get("detailUrl") or prop.get("url") or item.get("detailUrl")
    print(f"\nzpid = {zpid} | detailUrl = {detail_url}")

    base = ZillowClient.BASE_URL
    headers = client.headers
    probes = [
        ("/property", {"zpid": zpid}),
        ("/property/details", {"zpid": zpid}),
        ("/propertyDetails", {"zpid": zpid}),
        ("/property/byzpid", {"zpid": zpid}),
        ("/property/byZpid", {"zpid": zpid}),
        ("/byzpid", {"zpid": zpid}),
        ("/property", {"byzpid": zpid}),
        ("/property", {"property_id": zpid}),
        ("/home", {"zpid": zpid}),
        ("/getProperty", {"zpid": zpid}),
        (f"/property/{zpid}", None),
        ("/propertyV2", {"zpid": zpid}),
        ("/property/detail", {"zpid": zpid}),
    ]
    if detail_url:
        probes += [
            ("/property", {"url": detail_url}),
            ("/property/byurl", {"url": detail_url}),
            ("/property/byUrl", {"url": detail_url}),
        ]

    print("\n=== endpoint probes (status :: first 160 chars) ===")
    for path, params in probes:
        url = f"{base}{path}"
        try:
            r = requests.get(url, headers=headers, params=params, timeout=20)
            body = r.text[:160].replace("\n", " ")
            print(f"{r.status_code}  {path}  params={params}  :: {body}")
        except Exception as e:  # noqa: BLE001
            print(f"ERR  {path}  params={params}  :: {e}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
