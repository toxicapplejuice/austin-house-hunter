"""End-to-end pipeline test with mocked Zillow API + email (no network, no key).

Proves the orchestration wiring: search -> filter -> enrich -> geo pre-filter ->
fail-closed pool exclusion + school extraction -> bucket selection -> email. Runs
against the real config.yaml buckets but isolates all data-file writes to a tmp dir.
"""

import main as m

ROUND_ROCK = (30.508, -97.685)
TARRYTOWN = (30.305, -97.770)
KYLE = (29.989, -97.877)


def _raw(zpid, lat, lon, price=800_000, city="Austin"):
    return {
        "zpid": zpid,
        "address": {"streetAddress": f"{zpid} Test St", "city": city, "state": "TX", "zipcode": "78750"},
        "location": {"latitude": lat, "longitude": lon},
        "price": price,
        "bedrooms": 4,
        "bathrooms": 3,
        "livingArea": 2500,
        "homeType": "SINGLE_FAMILY",
        "daysOnZillow": 5,
    }


SEARCH_RESULTS = [
    _raw("RR1", *ROUND_ROCK, city="Round Rock"),    # bucket A, pool-free, Westwood-zoned
    _raw("POOL", *ROUND_ROCK, city="Round Rock"),   # has a pool -> excluded
    _raw("UNK", *ROUND_ROCK, city="Round Rock"),    # unknown pool status -> excluded (fail closed)
    _raw("TT1", TARRYTOWN[0], TARRYTOWN[1], price=1_800_000),  # bucket B
    _raw("FAR", *KYLE, city="Kyle"),                # far away -> dropped by geo pre-filter
]

DETAILS = {
    "RR1": {"property": {"resoFacts": {"hasPrivatePool": False, "highSchool": "Westwood High School"}}},
    "POOL": {"property": {"resoFacts": {"hasPrivatePool": True, "highSchool": "Westwood High School"}}},
    "UNK": {"property": {"resoFacts": {}}},  # no pool data -> check_has_pool returns None
    "TT1": {"property": {"resoFacts": {"hasPrivatePool": False, "highSchool": "Austin High School"}}},
    "FAR": {"property": {"resoFacts": {"hasPrivatePool": False}}},
}

_captured: list = []


class FakeZillow:
    def __init__(self, *a, **k):
        pass

    def build_search_prompt(self, config, neighborhood=None, location_override=None):
        return location_override or neighborhood or config.get("location", "Austin, TX")

    def search_by_prompt(self, prompt, page=1, sort_order="Newest"):
        results = SEARCH_RESULTS if page == 1 else []
        return {"props": results, "pagesInfo": {"totalPages": 1}}

    @staticmethod
    def extract_search_results(response):
        return response.get("props", []), response.get("pagesInfo", {}).get("totalPages", 1)

    def get_property_details(self, zpid):
        return DETAILS.get(zpid)


class FakeEmail:
    def __init__(self, *a, **k):
        pass

    def send_listings(self, recipient, new_listings, favorites, preferences):
        _captured.append(new_listings)
        return True


def test_pipeline_excludes_pools_and_fills_buckets(monkeypatch, tmp_path):
    _captured.clear()
    monkeypatch.setattr(m, "ZillowClient", FakeZillow)
    monkeypatch.setattr(m, "EmailSender", FakeEmail)
    monkeypatch.setattr(m, "DATA_DIR", tmp_path)   # isolate all data-file writes
    monkeypatch.setattr(m, "TESTING_MODE", True)
    monkeypatch.setenv("RAPIDAPI_KEY", "test")
    monkeypatch.setenv("GMAIL_ADDRESS", "x@y.com")
    monkeypatch.setenv("GMAIL_APP_PASSWORD", "pw")
    monkeypatch.setenv("RECIPIENT_EMAIL", "to@y.com")
    monkeypatch.delenv("RECIPIENT_EMAIL_2", raising=False)

    assert m.main() == 0

    assert len(_captured) == 1, "exactly one recipient should have been emailed"
    new = _captured[0]
    zpids = {l["zpid"] for l in new}

    # Pool home and unknown-pool home are both gone; far-away home was pre-filtered.
    assert zpids == {"RR1", "TT1"}, zpids
    assert not any(l.get("has_pool") is True for l in new)

    by = {l["zpid"]: l for l in new}
    assert by["RR1"]["bucket"] == "Round Rock / Westwood-Zoned"
    assert "Westwood" in (by["RR1"].get("high_school") or "")
    assert by["TT1"]["bucket"] == "Westlake & Central"
