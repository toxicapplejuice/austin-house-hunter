"""Bucket assignment, coarse gating, ranking, and selection."""

from buckets import (
    bucket_score,
    coarse_bucket_candidate,
    matches_bucket,
    select_bucketed,
)

BUCKET_A = {
    "name": "Round Rock / Westwood-Zoned",
    "count": 6,
    "max_price": 1_200_000,
    "match": {
        "high_schools": ["Westwood"],
        "cities": ["Round Rock"],
        "neighborhoods": ["Round Rock", "Anderson Mill", "Jollyville"],
    },
    "relax_neighborhoods": ["Cedar Park", "Great Hills"],
    "coarse_neighborhoods": ["Round Rock", "Anderson Mill", "Great Hills"],
    "coarse_radius_miles": 8,
}
BUCKET_B = {
    "name": "Westlake & Central",
    "count": 4,
    "max_price": 2_500_000,
    "match": {
        "high_schools": ["Westlake"],
        "cities": ["West Lake Hills", "Rollingwood"],
        "neighborhoods": ["West Lake Hills", "Tarrytown", "Clarksville"],
    },
    "relax_neighborhoods": ["Zilker", "Rosedale"],
    "coarse_neighborhoods": ["West Lake Hills", "Tarrytown", "Clarksville"],
    "coarse_radius_miles": 4,
}
BUCKETS = [BUCKET_A, BUCKET_B]

MIN_PRICE = 650_000


# --- matches_bucket ------------------------------------------------------------

def test_match_by_high_school():
    assert matches_bucket({"high_school": "Westwood High School", "price": 800_000}, BUCKET_A)


def test_match_by_city():
    assert matches_bucket({"city": "Round Rock", "price": 750_000}, BUCKET_A)


def test_match_by_neighborhood():
    assert matches_bucket({"neighborhood": "Anderson Mill", "price": 700_000}, BUCKET_A)


def test_no_match_other_area():
    listing = {"neighborhood": "South Austin", "city": "Austin",
               "price": 700_000, "high_school": "Akins High School"}
    assert not matches_bucket(listing, BUCKET_A)
    assert not matches_bucket(listing, BUCKET_B)


def test_price_cap_excludes_over_cap_round_rock():
    # A $1.5M Round Rock / Westwood home exceeds bucket A's $1.2M cap, and it's
    # not central, so it belongs to NO bucket and gets dropped.
    listing = {"city": "Round Rock", "high_school": "Westwood High School", "price": 1_500_000}
    assert not matches_bucket(listing, BUCKET_A)
    assert not matches_bucket(listing, BUCKET_B)


def test_premium_cap_allows_westlake():
    assert matches_bucket({"neighborhood": "Tarrytown", "price": 1_950_000}, BUCKET_B)


def test_relaxed_neighborhood_only_when_relaxed():
    listing = {"neighborhood": "Great Hills", "price": 800_000}
    assert not matches_bucket(listing, BUCKET_A, relaxed=False)
    assert matches_bucket(listing, BUCKET_A, relaxed=True)


def test_match_is_case_insensitive_for_school_and_city():
    assert matches_bucket({"high_school": "westwood hs", "price": 800_000}, BUCKET_A)
    assert matches_bucket({"city": "round rock", "price": 800_000}, BUCKET_A)


# --- coarse_bucket_candidate ---------------------------------------------------

def test_coarse_true_for_target_neighborhood():
    listing = {"neighborhood": "Round Rock", "latitude": 30.508, "longitude": -97.685}
    assert coarse_bucket_candidate(listing, BUCKETS)


def test_coarse_true_by_radius_for_nw_austin():
    # A Westwood-zoned NW-Austin home labeled "Great Hills" sits within bucket A's
    # coarse radius, so it survives to the (school-aware) detail step.
    listing = {"neighborhood": "Great Hills", "latitude": 30.41, "longitude": -97.758}
    assert coarse_bucket_candidate(listing, BUCKETS)


def test_coarse_false_for_far_away():
    listing = {"neighborhood": "Kyle", "city": "Kyle", "latitude": 29.989, "longitude": -97.877}
    assert not coarse_bucket_candidate(listing, BUCKETS)


# --- bucket_score --------------------------------------------------------------

def test_score_cheaper_ranks_higher():
    cheap = {"price": 700_000, "days_on_market": 5}
    pricey = {"price": 1_150_000, "days_on_market": 5}
    assert bucket_score(cheap, BUCKET_A, MIN_PRICE) > bucket_score(pricey, BUCKET_A, MIN_PRICE)


def test_score_newer_ranks_higher():
    new = {"price": 800_000, "days_on_market": 1}
    old = {"price": 800_000, "days_on_market": 90}
    assert bucket_score(new, BUCKET_A, MIN_PRICE) > bucket_score(old, BUCKET_A, MIN_PRICE)


def test_score_ignores_distance_to_downtown():
    near = {"price": 800_000, "days_on_market": 10, "distance": 1.0}
    far = {"price": 800_000, "days_on_market": 10, "distance": 25.0}
    assert bucket_score(near, BUCKET_A, MIN_PRICE) == bucket_score(far, BUCKET_A, MIN_PRICE)


# --- select_bucketed -----------------------------------------------------------

def _mk(zpid, **kw):
    listing = {"zpid": str(zpid), "price": 800_000, "days_on_market": 10}
    listing.update(kw)
    return listing


def test_select_fills_both_buckets_to_6_and_4():
    listings = (
        [_mk(i, city="Round Rock") for i in range(8)]
        + [_mk(100 + i, neighborhood="Tarrytown", price=1_800_000) for i in range(6)]
    )
    out = select_bucketed(listings, BUCKETS, MIN_PRICE)
    assert len([l for l in out if l["bucket"] == BUCKET_A["name"]]) == 6
    assert len([l for l in out if l["bucket"] == BUCKET_B["name"]]) == 4
    assert len(out) == 10


def test_select_underfill_sends_fewer_no_crossfill():
    listings = [
        _mk(1, city="Round Rock"),
        _mk(2, city="Round Rock"),
        _mk(3, neighborhood="Tarrytown", price=1_800_000),
    ]
    out = select_bucketed(listings, BUCKETS, MIN_PRICE)
    assert len([l for l in out if l["bucket"] == BUCKET_A["name"]]) == 2
    assert len([l for l in out if l["bucket"] == BUCKET_B["name"]]) == 1
    assert len(out) == 3


def test_select_relaxes_when_strict_is_short():
    listings = (
        [_mk(i, city="Round Rock") for i in range(3)]
        + [_mk(50 + i, neighborhood="Great Hills") for i in range(10)]  # relax-only matches
    )
    out = select_bucketed(listings, BUCKETS, MIN_PRICE)
    assert len([l for l in out if l["bucket"] == BUCKET_A["name"]]) == 6  # 3 strict + 3 relaxed


def test_select_never_cross_fills():
    listings = [_mk(i, city="Round Rock") for i in range(20)]
    out = select_bucketed(listings, BUCKETS, MIN_PRICE)
    assert len([l for l in out if l["bucket"] == BUCKET_A["name"]]) == 6
    assert len([l for l in out if l["bucket"] == BUCKET_B["name"]]) == 0
    assert len(out) == 6


def test_select_ranks_cheaper_first_within_bucket():
    listings = [
        _mk(1, city="Round Rock", price=1_150_000, days_on_market=5),
        _mk(2, city="Round Rock", price=700_000, days_on_market=5),
    ]
    out = select_bucketed(listings, BUCKETS, MIN_PRICE)
    assert out[0]["zpid"] == "2"
