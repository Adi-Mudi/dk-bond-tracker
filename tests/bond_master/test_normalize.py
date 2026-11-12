import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import pytest

from src.bond_master.normalize import (
    CANONICAL_CYCLES,
    is_investment_grade,
    is_valid_isin,
    normalize_cycle,
    normalize_isin,
    rating_band,
)

VALID_ISIN = "INE205A07DV2"


def test_isin_valid_shape_accepted():
    assert is_valid_isin(VALID_ISIN) is True
    assert normalize_isin(VALID_ISIN) == VALID_ISIN


def test_isin_lowercase_is_uppercased():
    assert normalize_isin("ine205a07dv2") == VALID_ISIN
    assert is_valid_isin("ine205a07dv2") is True


def test_isin_surrounding_whitespace_is_trimmed():
    assert normalize_isin("  INE205A07DV2  ") == VALID_ISIN


def test_isin_wrong_length_rejected():
    assert normalize_isin("INE205A07DV") is None
    assert normalize_isin("INE205A07DV22") is None
    assert is_valid_isin("") is False


def test_isin_bad_shape_rejected():
    assert normalize_isin("1NE205A07DV2") is None
    assert normalize_isin("INE205A07DVX") is None
    assert normalize_isin("IN-205A07DV2") is None


def test_isin_non_string_and_blank_rejected():
    assert normalize_isin(None) is None
    assert normalize_isin("   ") is None
    assert is_valid_isin(None) is False


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("monthly", "monthly"),
        ("Monthly", "monthly"),
        (" MONTHLY ", "monthly"),
        ("quarterly", "quarterly"),
        ("Quarterly", "quarterly"),
        ("yearly", "annual"),
        (" YEARLY ", "annual"),
        ("Yearly", "annual"),
        ("annual", "annual"),
        ("Annual", "annual"),
        (" ANN UAL ", None),
    ],
)
def test_cycle_normalization_accepts_every_variant(raw, expected):
    assert normalize_cycle(raw) == expected


def test_cycle_yearly_alias_never_emits_yearly():
    assert normalize_cycle("yearly") == "annual"
    assert normalize_cycle("YEARLY") != "yearly"


def test_cycle_unknown_and_blank_return_none():
    assert normalize_cycle("semi_annual") is None
    assert normalize_cycle("weekly") is None
    assert normalize_cycle("fortnightly") is None
    assert normalize_cycle("") is None
    assert normalize_cycle("   ") is None
    assert normalize_cycle(None) is None


def test_cycle_output_is_always_canonical():
    for raw in (
        "monthly",
        "quarterly",
        "yearly",
        "annual",
        "MONTHLY",
        " YEARLY ",
        "Annual",
    ):
        assert normalize_cycle(raw) in CANONICAL_CYCLES


@pytest.mark.parametrize(
    "rating",
    ["AAA", "AA+", "AA", "AA-", "A+", "A", "A-", "BBB+", "BBB", "BBB-"],
)
def test_investment_grade_ratings_accepted(rating):
    assert is_investment_grade(rating) is True


@pytest.mark.parametrize(
    "rating",
    ["BB+", "BB", "BB-", "B+", "B", "B-", "CCC", "CC", "C", "D"],
)
def test_below_investment_grade_refused(rating):
    assert is_investment_grade(rating) is False
    assert rating_band(rating) is None


@pytest.mark.parametrize("rating", ["", "   ", None, "unrated", "NR"])
def test_unrated_is_not_investment_grade(rating):
    assert is_investment_grade(rating) is False


def test_rating_band_returns_the_band_without_modifier():
    assert rating_band("AAA") == "AAA"
    assert rating_band("AA+") == "AA"
    assert rating_band("A-") == "A"
    assert rating_band("BBB-") == "BBB"


@pytest.mark.parametrize(
    "rating",
    ["CRISIL AA+", "ICRA A", "CARE BBB-", "IND AA", "BWR AAA", "crisil aa+"],
)
def test_rating_accepts_agency_prefix_and_case(rating):
    assert is_investment_grade(rating) is True


def test_rating_agency_prefix_below_grade_refused():
    assert is_investment_grade("CRISIL BB+") is False
    assert is_investment_grade("ICRA D") is False
