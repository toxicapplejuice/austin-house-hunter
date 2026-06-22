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
    prop = item.get("property", item)
    zpid = prop.get("zpid") or item.get("zpid")

    needles = ["pool", "school", "reso", "atagl", "homefact", "amenit",
               "feature", "district", "descr", "hdpdata", "hometype", "fact"]

    def find_keys(obj, path=""):
        hits = []
        if isinstance(obj, dict):
            for k, v in obj.items():
                kp = f"{path}.{k}"
                if any(n in str(k).lower() for n in needles):
                    shown = v if not isinstance(v, (dict, list)) else f"{type(v).__name__}({len(v)})"
                    hits.append((kp, shown))
                hits += find_keys(v, kp)
        elif isinstance(obj, list):
            for i, v in enumerate(obj[:4]):
                hits += find_keys(v, f"{path}[{i}]")
        return hits

    # Strip the giant photo arrays so the rest of the item is visible.
    slim = json.loads(json.dumps(item))
    try:
        del slim["property"]["media"]
    except Exception:  # noqa: BLE001
        pass

    print("=== search item: property.* keys ===")
    print(sorted(prop.keys()))
    print("\n=== search item: pool/school/descr key paths ===")
    for kp, shown in find_keys(item):
        print(f"  {kp} = {str(shown)[:200]}")
    print("\n=== search item (media stripped, truncated) ===")
    print(json.dumps(slim, indent=2)[:7000])
    print(f"\nzpid = {zpid}")

    # Confirmed working detail endpoint: /byzpid?zpid=...
    r = requests.get(
        f"{ZillowClient.BASE_URL}/byzpid",
        headers=client.headers,
        params={"zpid": zpid},
        timeout=30,
    )
    print(f"\n=== /byzpid status {r.status_code} ===")
    try:
        detail = r.json()
    except Exception as e:  # noqa: BLE001
        print("not JSON:", e, r.text[:500])
        return 1

    print("top-level keys:", sorted(detail.keys()) if isinstance(detail, dict) else type(detail).__name__)

    needles = ["pool", "school", "reso", "atagl", "homefact", "amenit", "feature", "district"]

    def find_keys(obj, path=""):
        hits = []
        if isinstance(obj, dict):
            for k, v in obj.items():
                kp = f"{path}.{k}"
                if any(n in str(k).lower() for n in needles):
                    shown = v if not isinstance(v, (dict, list)) else f"{type(v).__name__}({len(v)})"
                    hits.append((kp, shown))
                hits += find_keys(v, kp)
        elif isinstance(obj, list):
            for i, v in enumerate(obj[:4]):
                hits += find_keys(v, f"{path}[{i}]")
        return hits

    print("\n=== pool/school/feature key paths ===")
    for kp, shown in find_keys(detail):
        print(f"  {kp} = {str(shown)[:160]}")

    print("\n=== full /byzpid JSON (truncated) ===")
    print(json.dumps(detail, indent=2)[:9000])
    return 0


if __name__ == "__main__":
    sys.exit(main())
