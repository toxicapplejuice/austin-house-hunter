"""End-to-end pipeline test with mocked search + vision + email (no network).

Proves the orchestration: search -> filter -> enrich -> geo pre-filter -> vision
pool exclusion (fail closed) -> bucket fill -> email. Runs against the real
config.yaml buckets but isolates all data-file writes to a tmp dir and stubs the
vision call (no Anthropic API hit).
"""

import main as m

ROUND_ROCK = (30.508, -97.685)
TARRYTOWN = (30.305, -97.770)
KYLE = (29.989, -97.877)


def _raw(zpid, lat, lon, price=800_000, city="Austin", photos=None):
    return {
        "zpid": zpid,
        "address": {"streetAddress": f"{zpid} Test St", "city": city, "state": "TX", "zipcode": "78717"},
        "location": {"latitude": lat, "longitude": lon},
        "media": {"allPropertyPhotos": {"medium": photos or [f"http://photo/{zpid}.jpg"]}},
        "price": {"value": price},
        "bedrooms": 4,
        "bathrooms": 3,
        "livingArea": 2500,
        "homeType": "SINGLE_FAMILY",
        "daysOnZillow": 5,
    }


SEARCH_RESULTS = [
    _raw("RR1", *ROUND_ROCK, city="Round Rock"),                       # bucket A, pool-free
    _raw("POOL", *ROUND_ROCK, city="Round Rock", photos=["http://x/HASPOOL.jpg"]),  # excluded
    _raw("UNK", *ROUND_ROCK, city="Round Rock", photos=["http://x/UNKNOWN.jpg"]),   # fail-closed
    _raw("TT1", TARRYTOWN[0], TARRYTOWN[1], price=1_800_000),          # bucket B
    _raw("FAR", *KYLE, city="Kyle"),                                   # geo pre-filtered out
]

_captured: list = []


class FakeZillow:
    def __init__(self, *a, **k):
        pass

    def build_search_prompt(self, config, neighborhood=None, location_override=None):
        return location_override or neighborhood or config.get("location", "Austin, TX")

    def search_by_prompt(self, prompt, page=1, sort_order="Newest"):
        return {"props": SEARCH_RESULTS if page == 1 else [], "pagesInfo": {"totalPages": 1}}

    @staticmethod
    def extract_search_results(response):
        return response.get("props", []), response.get("pagesInfo", {}).get("totalPages", 1)

    def get_property_details(self, zpid):  # only used for favorite stubs (none here)
        return None


class FakeEmail:
    def __init__(self, *a, **k):
        pass

    def send_listings(self, recipient, new_listings, favorites, preferences):
        _captured.append(new_listings)
        return True


def _fake_detect(photo_urls, **kwargs):
    urls = photo_urls or []
    if any("HASPOOL" in u for u in urls):
        return True, "pool"
    if any("UNKNOWN" in u for u in urls):
        return None, "unsure"
    return False, "no pool"


def test_pipeline_vision_excludes_pools_and_fills_buckets(monkeypatch, tmp_path):
    _captured.clear()
    monkeypatch.setattr(m, "ZillowClient", FakeZillow)
    monkeypatch.setattr(m, "EmailSender", FakeEmail)
    monkeypatch.setattr(m, "DATA_DIR", tmp_path)
    monkeypatch.setattr(m, "TESTING_MODE", True)
    monkeypatch.setattr(m, "detect_pool_from_photos", _fake_detect)
    monkeypatch.setenv("RAPIDAPI_KEY", "test")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test")
    monkeypatch.setenv("GMAIL_ADDRESS", "x@y.com")
    monkeypatch.setenv("GMAIL_APP_PASSWORD", "pw")
    monkeypatch.setenv("RECIPIENT_EMAIL", "to@y.com")
    monkeypatch.delenv("RECIPIENT_EMAIL_2", raising=False)

    assert m.main() == 0

    assert len(_captured) == 1
    new = _captured[0]
    zpids = {l["zpid"] for l in new}

    # Pool home and unknown-pool home are both gone; far-away home was pre-filtered.
    assert zpids == {"RR1", "TT1"}, zpids
    assert not any(l.get("has_pool") is True for l in new)

    by = {l["zpid"]: l for l in new}
    assert by["RR1"]["bucket"] == "Round Rock / Westwood-Zoned"
    assert by["TT1"]["bucket"] == "Westlake & Central"
