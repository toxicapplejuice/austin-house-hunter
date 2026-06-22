"""Geographic bucket assignment, ranking, and selection.

The bot now fills two explicit, geography-driven buckets per email instead of a
single relevance-ranked list:

  - Bucket A: homes zoned to Westwood HS (precise, via the listing's assigned
    high school) or, failing that, in Round Rock / the NW Round Rock ISD corridor.
  - Bucket B: homes in Westlake / Tarrytown / Clarksville and adjacent central-west
    neighborhoods.

Each bucket has its own price cap (Round Rock is affordable; the central-west
areas are not), a desired ``count``, and a ``relax_neighborhoods`` widening used
only when strict matches can't fill the bucket. When a bucket still can't fill
after relaxing, we send fewer rather than cross-filling from the other bucket.

This module is intentionally free of API/IO so it is cheap to unit-test.
"""

from typing import Any

from location import NEIGHBORHOODS, haversine_distance
from zillow_client import passes_pool_filter

DEFAULT_COARSE_RADIUS_MILES = 5.0


def _text_contains_any(value: Any, candidates: list[str]) -> bool:
    """Case-insensitive substring match of ``value`` against any candidate."""
    if not value or not candidates:
        return False
    v = str(value).lower()
    return any(c and c.lower() in v for c in candidates)


def matches_bucket(listing: dict[str, Any], bucket: dict[str, Any], relaxed: bool = False) -> bool:
    """Return True if ``listing`` belongs in ``bucket`` (precise, post-detail match).

    Order of evidence: zoned high school (most precise) → city → neighborhood.
    The bucket's ``max_price`` is enforced first, so an over-cap home matches no
    bucket and is dropped (e.g. a $1.5M Round Rock home).
    """
    max_price = bucket.get("max_price")
    price = listing.get("price")
    if max_price and price and price > max_price:
        return False

    match = bucket.get("match", {})

    # 1. Zoned high school — the precise signal (e.g. "Westwood", "Westlake").
    if _text_contains_any(listing.get("high_school"), match.get("high_schools", [])):
        return True

    # 2. City (e.g. "Round Rock").
    if _text_contains_any(listing.get("city"), match.get("cities", [])):
        return True

    # 3. Neighborhood — exact set; relaxed mode widens to relax_neighborhoods.
    neighborhoods = list(match.get("neighborhoods", []))
    if relaxed:
        neighborhoods += bucket.get("relax_neighborhoods", [])
    nb = listing.get("neighborhood")
    if nb and nb in neighborhoods:
        return True

    return False


def coarse_bucket_candidate(
    listing: dict[str, Any],
    buckets: list[dict[str, Any]],
    radius_miles: float | None = None,
) -> bool:
    """Cheap pre-detail gate: could this home plausibly land in any bucket?

    Used before the expensive per-listing property-detail fetch so we only spend
    API calls on geographically relevant homes. Conservative on purpose — it does
    NOT use the (not-yet-fetched) high school, so it relies on city/neighborhood
    text plus a geographic radius around each bucket's anchor neighborhoods. A
    Westwood-zoned NW-Austin home sits inside that radius, so it survives to the
    detail step where its school upgrades it from "Round Rock corridor" to
    "Westwood-zoned".
    """
    lat = listing.get("latitude")
    lon = listing.get("longitude")
    nb = listing.get("neighborhood")

    for bucket in buckets:
        match = bucket.get("match", {})
        if _text_contains_any(listing.get("city"), match.get("cities", [])):
            return True

        names = (
            set(match.get("neighborhoods", []))
            | set(bucket.get("relax_neighborhoods", []))
            | set(bucket.get("coarse_neighborhoods", []))
        )
        if nb and nb in names:
            return True

        if lat and lon:
            radius = radius_miles or bucket.get("coarse_radius_miles") or DEFAULT_COARSE_RADIUS_MILES
            for name in names:
                centroid = NEIGHBORHOODS.get(name)
                if centroid and haversine_distance(lat, lon, centroid[0], centroid[1]) <= radius:
                    return True

    return False


def bucket_score(listing: dict[str, Any], bucket: dict[str, Any], min_price: float | None) -> float:
    """Rank homes WITHIN a bucket. Deliberately omits distance-to-downtown — the
    bucket already defines the desired area, and penalizing distance would unfairly
    sink the (intentionally far) Round Rock homes. Cheaper + newer ranks higher.
    """
    min_price = min_price or 0
    price = listing.get("price") or 0
    max_price = bucket.get("max_price") or (price * 2 if price else 1_000_000)
    if max_price > min_price:
        price_score = 100 - ((price - min_price) / (max_price - min_price)) * 100
        price_score = max(0, min(100, price_score))
    else:
        price_score = 50

    days = listing.get("days_on_market")
    days = days if days is not None else 30
    newness_score = max(0, 100 - (days / 60) * 100)

    return 0.5 * price_score + 0.5 * newness_score


def _key(listing: dict[str, Any]) -> Any:
    """Stable identity for dedup across buckets (zpid, else object identity)."""
    return listing.get("zpid") or id(listing)


def _ranked(
    items: list[dict[str, Any]], bucket: dict[str, Any], min_price: float | None
) -> list[dict[str, Any]]:
    for item in items:
        item["bucket_score"] = bucket_score(item, bucket, min_price)
    return sorted(items, key=lambda x: x.get("bucket_score", 0), reverse=True)


def fill_buckets(
    listings: list[dict[str, Any]],
    buckets: list[dict[str, Any]],
    min_price: float | None = None,
    pool_check: Any = None,
    max_pool_checks: int | None = None,
) -> list[dict[str, Any]]:
    """Fill each bucket up to its ``count``, ranked by ``bucket_score``.

    Strict matches first; if short, widen to ``relax_neighborhoods``; if still
    short, take fewer (never cross-fill from the other bucket).

    When ``pool_check`` is given it is called LAZILY — only on candidates we're
    about to select, in ranked order — so paid pool checks are minimized. The
    signature is ``pool_check(listing) -> (has_pool, reason)``; a home passes only
    if confirmed pool-free (fail closed: True or None are dropped). ``max_pool_checks``
    caps total checks; once hit, unchecked candidates are treated as unknown.

    Mutates chosen listings with ``bucket``/``bucket_score`` and any checked listing
    with ``has_pool``/``pool_reason``. Returns a flat list ordered by bucket order.
    """
    selected: list[dict[str, Any]] = []
    used: set[Any] = set()
    cache: dict[Any, bool | None] = {}
    checks = {"n": 0}

    def _passes_pool(listing: dict[str, Any]) -> bool:
        if pool_check is None:
            return True
        k = _key(listing)
        if k not in cache:
            if max_pool_checks is not None and checks["n"] >= max_pool_checks:
                has_pool, reason = None, "pool-check budget exhausted"
            else:
                has_pool, reason = pool_check(listing)
                checks["n"] += 1
            cache[k] = has_pool
            listing["has_pool"] = has_pool
            listing["pool_reason"] = reason
        return passes_pool_filter(cache[k], exclude_pool=True)

    for bucket in buckets:
        name = bucket.get("name", "")
        count = bucket.get("count", 0)
        chosen: list[dict[str, Any]] = []

        for relaxed in (False, True):
            if len(chosen) >= count:
                break
            ranked = _ranked(
                [l for l in listings if _key(l) not in used and matches_bucket(l, bucket, relaxed)],
                bucket,
                min_price,
            )
            for cand in ranked:
                if len(chosen) >= count:
                    break
                if _passes_pool(cand):
                    cand["bucket"] = name
                    used.add(_key(cand))
                    chosen.append(cand)

        selected.extend(chosen)

    return selected


def select_bucketed(
    listings: list[dict[str, Any]],
    buckets: list[dict[str, Any]],
    min_price: float | None = None,
) -> list[dict[str, Any]]:
    """Bucket selection with no pool filtering (thin wrapper over fill_buckets)."""
    return fill_buckets(listings, buckets, min_price, pool_check=None)
