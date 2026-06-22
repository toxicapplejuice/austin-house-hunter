"""ListingFilter behavior with the raised $2.5M global price ceiling."""

from filters import ListingFilter

CONFIG = {
    "min_price": 650_000,
    "max_price": 2_500_000,
    "min_beds": 3,
    "min_baths": 2,
    "min_sqft": 1_000,
    "property_types": ["single_family"],
    "exclude_features": ["pool"],
}


def _home(**kw):
    home = {
        "price": 800_000,
        "beds": 4,
        "baths": 3,
        "sqft": 2_000,
        "property_type": "single_family",
        "has_pool": False,
    }
    home.update(kw)
    return home


def test_premium_home_passes_at_2_4m():
    assert ListingFilter(CONFIG).matches(_home(price=2_400_000, sqft=3_500)) is True


def test_over_global_max_rejected():
    assert ListingFilter(CONFIG).matches(_home(price=2_600_000)) is False


def test_under_min_price_rejected():
    assert ListingFilter(CONFIG).matches(_home(price=500_000)) is False


def test_too_few_beds_rejected():
    assert ListingFilter(CONFIG).matches(_home(beds=2)) is False


def test_confirmed_pool_rejected_by_filter():
    assert ListingFilter(CONFIG).matches(_home(has_pool=True)) is False


def test_pool_in_description_rejected_when_status_unknown():
    home = _home(has_pool=None, description="Stunning home with a heated pool")
    assert ListingFilter(CONFIG).matches(home) is False


def test_typical_round_rock_home_passes():
    assert ListingFilter(CONFIG).matches(_home(price=850_000)) is True
