import pytest
pytest.skip("Retired per issue #337: old frontend removal", allow_module_level=True)
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEMPLATES = ROOT / "src" / "templates"
CSS = (ROOT / "src" / "static" / "theme.css").read_text(encoding="utf-8")
CHIP_LINE = next(
    line
    for line in (TEMPLATES / "watch.html").read_text(encoding="utf-8").splitlines()
    if "chip chip-rating" in line
)
ARROWS = ("\u25b2", "\u25bc")


def token(block_selector, name):
    start = CSS.index(block_selector)
    end = CSS.index("}", start)
    match = re.search(rf"{re.escape(name)}:\s*(#[0-9a-fA-F]{{6}})", CSS[start:end])
    assert match, f"{name} missing in {block_selector}"
    return match.group(1).lower()


def rule_body(selector):
    match = re.search(rf"^{re.escape(selector)}\s*\{{([^}}]*)\}}", CSS, re.M)
    assert match, selector
    return match.group(1)


def test_rs06_rating_chip_shows_grade_text_only():
    assert "{{ candidate.rating or 'Not rated' }}" in CHIP_LINE
    chip_text = CHIP_LINE.split(">", 1)[1].rsplit("</span>", 1)[0]
    assert chip_text.strip() == "{{ candidate.rating or 'Not rated' }}"
    for arrow in ARROWS:
        assert arrow not in CHIP_LINE


def test_rs06_no_outlook_or_arrow_markup_in_rating_chips():
    for template in TEMPLATES.glob("*.html"):
        for line in template.read_text(encoding="utf-8").splitlines():
            if "chip-rating" not in line:
                continue
            assert "outlook" not in line.lower(), template.name
            assert "chip-outlook" not in line, template.name
            for arrow in ARROWS:
                assert arrow not in line, template.name


def test_rs06_band_mapping_matches_d5():
    assert "r.startswith('AAA') or r in ['AA+', 'AA', 'AA-']" in CHIP_LINE
    assert "chip-rating-aaa" in CHIP_LINE
    assert "r in ['A+', 'A', 'A-'] %}chip-rating-a{%" in CHIP_LINE
    assert (
        "r in ['BBB+', 'BBB', 'BBB-', 'BB+', 'BB', 'BB-', 'B+', 'B', 'B-', 'C', 'D'] %}chip-rating-amber"
        in CHIP_LINE
    )
    assert "else %}chip-rating-none" in CHIP_LINE


def test_rs06_band_colours_are_green_blue_amber_grey_not_red():
    assert "var(--ongoing-fg)" in rule_body(".chip-rating-aaa")
    assert "var(--watching-fg)" in rule_body(".chip-rating-a")
    assert "var(--warn-fg)" in rule_body(".chip-rating-amber")
    assert "var(--matured-fg)" in rule_body(".chip-rating-none")
    for selector in (".chip-rating-aaa", ".chip-rating-a", ".chip-rating-amber", ".chip-rating-none"):
        assert not re.search(r"\bred\b", rule_body(selector).lower()), selector
    for block in ('html[data-theme="light"]', 'html[data-theme="dark"]', 'html[data-theme="system"]'):
        red, green, blue = (int(token(block, "--ongoing-fg")[i:i + 2], 16) for i in (1, 3, 5))
        assert green > red and green > blue, block


def test_rs06_chip_keeps_fixed_min_width():
    assert ".chip-rating { min-width: 6em; text-align: center; }" in CSS
