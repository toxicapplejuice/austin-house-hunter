"""Assigned-school extraction (extract_schools), defensive across API shapes."""

from zillow_client import extract_schools


def test_reso_high_school_string():
    details = {"property": {"resoFacts": {"highSchool": "Westwood High School"}}}
    assert extract_schools(details)["high_school"] == "Westwood High School"


def test_schools_array_high_by_level():
    details = {"property": {"schools": [
        {"name": "Westwood High School", "level": "High"},
        {"name": "Canyon Vista Middle", "level": "Middle"},
    ]}}
    assert extract_schools(details)["high_school"] == "Westwood High School"


def test_schools_array_high_by_grades():
    details = {"property": {"schools": [{"name": "Some High School", "grades": "9-12"}]}}
    assert extract_schools(details)["high_school"] == "Some High School"


def test_string_field_takes_precedence_over_array():
    details = {"property": {
        "resoFacts": {"highSchool": "Westwood High School"},
        "schools": [{"name": "Other High School", "level": "High"}],
    }}
    assert extract_schools(details)["high_school"] == "Westwood High School"


def test_district_extracted():
    details = {"property": {"resoFacts": {"schoolDistrict": "Round Rock ISD"}}}
    assert extract_schools(details)["district"] == "Round Rock ISD"


def test_schools_absent_is_none():
    out = extract_schools({"property": {}})
    assert out["high_school"] is None
    assert out["schools"] == []


def test_schools_malformed_is_safe():
    out = extract_schools({"property": {"schools": ["garbage", 5, None]}})
    assert out["high_school"] is None


def test_works_without_property_wrapper():
    # Some responses are flat (no nested "property" key).
    assert extract_schools({"resoFacts": {"highSchool": "Westlake High School"}})["high_school"] == "Westlake High School"
