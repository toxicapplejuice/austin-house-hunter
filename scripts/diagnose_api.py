"""One-off capability check (run in CI with the existing RAPIDAPI_KEY secret),
authorized by the user: does our current RapidAPI key already work on the richer
`zillow-com1` Zillow API, and does that API return pool + school data?

The current private-zillow API returns no pool/school data, so we plan to switch
to zillow-com1 (which exposes resoFacts.hasPrivatePool + a schools array). This
just confirms whether the existing key is already subscribed (zero setup) or a
subscription is needed. Sends NO email. Remove after the data source is settled.
"""

import json
import sys
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from zillow_client import ZillowClient  # noqa: E402

NEEDLES = ["pool", "school", "reso", "atagl", "homefact", "amenit",
           "feature", "district", "descr", "fact", "hometype"]

ALT_HOST = "zillow-com1.p.rapidapi.com"


def find_keys(obj, path=""):
    hits = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            kp = f"{path}.{k}"
            if any(n in str(k).lower() for n in NEEDLES):
                shown = v if not isinstance(v, (dict, list)) else f"{type(v).__name__}({len(v)})"
                hits.append((kp, shown))
            hits += find_keys(v, kp)
    elif isinstance(obj, list):
        for i, v in enumerate(obj[:4]):
            hits += find_keys(v, f"{path}[{i}]")
    return hits


def main() -> int:
    client = ZillowClient()
    resp = client.search_by_prompt("houses for sale in Round Rock, TX under $1.2M")
    results, _ = client.extract_search_results(resp)
    if not results:
        print("no search results")
        return 1
    zpid = results[0].get("property", results[0]).get("zpid")
    print(f"probe zpid = {zpid}\n")

    headers = {"x-rapidapi-key": client.api_key, "x-rapidapi-host": ALT_HOST}
    r = requests.get(
        f"https://{ALT_HOST}/property", headers=headers, params={"zpid": zpid}, timeout=30
    )
    print(f"=== {ALT_HOST}/property?zpid={zpid} ===")
    print("status:", r.status_code, "::", r.text[:240].replace("\n", " "))

    if r.status_code == 200:
        try:
            data = r.json()
        except Exception:  # noqa: BLE001
            print("(not JSON)")
            return 0
        print("\npool/school/feature key paths:")
        hits = find_keys(data)
        for kp, shown in hits:
            print(f"  {kp} = {str(shown)[:160]}")
        if not hits:
            print("  (none)")
        # Show the specific fields our parser needs.
        prop = data.get("property", data)
        reso = prop.get("resoFacts") or {}
        print("\nKEY FIELDS:")
        print("  resoFacts.hasPrivatePool =", reso.get("hasPrivatePool"))
        print("  resoFacts.poolFeatures   =", reso.get("poolFeatures"))
        print("  resoFacts.highSchool     =", reso.get("highSchool"))
        print("  schools                  =", json.dumps(prop.get("schools"))[:300])
    return 0


if __name__ == "__main__":
    sys.exit(main())
