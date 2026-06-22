"""Pool detection (check_has_pool) and the fail-closed gate (passes_pool_filter)."""

from zillow_client import check_has_pool, passes_pool_filter


# --- check_has_pool: the 7 detection tiers -------------------------------------

def test_has_private_pool_true():
    assert check_has_pool({"property": {"resoFacts": {"hasPrivatePool": True}}})[0] is True


def test_has_private_pool_false():
    assert check_has_pool({"property": {"resoFacts": {"hasPrivatePool": False}}})[0] is False


def test_pool_features_list_with_pool():
    details = {"property": {"resoFacts": {"poolFeatures": ["In Ground", "Gunite"]}}}
    assert check_has_pool(details)[0] is True


def test_pool_features_none():
    assert check_has_pool({"property": {"resoFacts": {"poolFeatures": ["None"]}}})[0] is False


def test_at_a_glance_pool_yes():
    details = {"property": {"atAGlanceFacts": [{"factLabel": "Pool", "factValue": "Yes"}]}}
    assert check_has_pool(details)[0] is True


def test_at_a_glance_pool_none():
    details = {"property": {"atAGlanceFacts": [{"factLabel": "Pool", "factValue": "None"}]}}
    assert check_has_pool(details)[0] is False


def test_home_facts_bool():
    assert check_has_pool({"property": {"homeFacts": {"hasPool": True}}})[0] is True


def test_features_list_pool():
    assert check_has_pool({"property": {"features": ["Private Pool", "Garage"]}})[0] is True


def test_features_pool_table_not_a_pool():
    # "pool table" is explicitly excluded, so this tier finds nothing -> unknown.
    assert check_has_pool({"property": {"features": ["Pool table in game room"]}})[0] is None


def test_amenities_pool():
    assert check_has_pool({"property": {"amenities": ["Community Pool"]}})[0] is True


def test_description_mentions_pool():
    details = {"property": {"description": "Beautiful home with a sparkling swimming pool"}}
    assert check_has_pool(details)[0] is True


def test_description_no_pool_negation():
    details = {"property": {"description": "Spacious yard, no pool, great for pets"}}
    assert check_has_pool(details)[0] is False


def test_unknown_when_no_pool_data():
    assert check_has_pool({"property": {"resoFacts": {}}})[0] is None


# --- passes_pool_filter: the fail-closed fix -----------------------------------

def test_confirmed_pool_free_passes():
    assert passes_pool_filter(False, exclude_pool=True) is True


def test_detected_pool_rejected():
    assert passes_pool_filter(True, exclude_pool=True) is False


def test_unknown_rejected_when_excluding():
    # THE bug fix: previously "unknown" was INCLUDED; now it is dropped.
    assert passes_pool_filter(None, exclude_pool=True) is False


def test_everything_passes_when_filter_off():
    assert passes_pool_filter(None, exclude_pool=False) is True
    assert passes_pool_filter(True, exclude_pool=False) is True
    assert passes_pool_filter(False, exclude_pool=False) is True
