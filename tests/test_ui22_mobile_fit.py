import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEMPLATES = ROOT / "src" / "templates"
STATIC = ROOT / "src" / "static"

REM = re.compile(r"([0-9]*\.?[0-9]+)rem")


def rules_of(text):
    found = []
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.S)

    def scan(block):
        pos = 0
        while pos < len(block):
            brace = block.find("{", pos)
            if brace == -1:
                break
            header = " ".join(block[pos:brace].split())
            depth = 1
            end = brace + 1
            while end < len(block) and depth:
                if block[end] == "{":
                    depth += 1
                elif block[end] == "}":
                    depth -= 1
                end += 1
            body = block[brace + 1 : end - 1]
            if header.startswith("@"):
                scan(body)
            elif header:
                found.append((header, body))
            pos = end

    scan(text)
    return found


def body_for(rules, selector):
    for header, body in rules:
        if selector in [part.strip() for part in header.split(",")]:
            return body
    return None


def min_height_rem(body):
    match = re.search(r"(?<![\w-])min-height\s*:\s*([0-9]*\.?[0-9]+)rem", body or "")
    return float(match.group(1)) if match else 0.0


def test_print_page_scrolls_inside_a_wrapper_instead_of_the_document():
    text = (TEMPLATES / "monthly_print.html").read_text(encoding="utf-8")
    assert '<div class="print-scroll">' in text
    body = body_for(rules_of(text), ".print-scroll")
    assert body is not None
    assert "overflow-x: auto" in body


def test_goals_checkin_buttons_are_tall_enough_to_tap():
    body = body_for(rules_of((TEMPLATES / "goals.html").read_text(encoding="utf-8")), ".checkin-month")
    assert body is not None
    assert min_height_rem(body) >= 2.0


def test_settings_details_summary_is_a_real_tap_target():
    body = body_for(rules_of((TEMPLATES / "settings.html").read_text(encoding="utf-8")), ".advanced-email summary")
    assert body is not None
    assert min_height_rem(body) >= 2.0


def test_setup_guide_summary_is_a_real_tap_target():
    body = body_for(rules_of((STATIC / "theme.css").read_text(encoding="utf-8")), ".setup-guide summary")
    assert body is not None
    assert min_height_rem(body) >= 2.0


def test_payment_toggle_rows_are_tall_enough_to_tap():
    text = (TEMPLATES / "payment_edit.html").read_text(encoding="utf-8")
    rules = rules_of(text)
    row = body_for(rules, ".field .checkbox-line")
    assert row is not None
    assert min_height_rem(row) >= 2.0
    box = body_for(rules, '.field input[type="checkbox"]')
    assert box is not None
    assert "width: 1.25rem" in box and "height: 1.25rem" in box


def test_guard_detects_missing_min_height():
    sample = ".checkin-month { padding: 2px 10px; }"
    assert min_height_rem(body_for(rules_of(sample), ".checkin-month")) == 0.0


def test_settings_checkbox_rows_are_tall_enough_to_tap():
    rules = rules_of((STATIC / "theme.css").read_text(encoding="utf-8"))
    row = body_for(rules, ".check-row")
    assert row is not None
    assert min_height_rem(row) >= 2.0
    box = body_for(rules, ".check-row input")
    assert box is not None
    assert "width: 1.25rem" in box and "height: 1.25rem" in box


def test_share_checkbox_rows_are_tall_enough_to_tap():
    rules = rules_of((TEMPLATES / "share.html").read_text(encoding="utf-8"))
    label = body_for(rules, ".share-checks label")
    assert label is not None
    assert min_height_rem(label) >= 2.0
    box = body_for(rules, ".share-checks input")
    assert box is not None
    assert "width: 1.25rem" in box and "height: 1.25rem" in box
