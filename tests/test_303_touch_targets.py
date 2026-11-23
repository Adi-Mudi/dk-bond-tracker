import pytest
import re
from pathlib import Path

from src.app import create_app
from src.db import get_conn
from tests.conftest import add_bond

ROOT = Path(__file__).resolve().parents[1]
STATIC = ROOT / "src" / "static"
TEMPLATES = ROOT / "src" / "templates"

STYLE_BLOCK = re.compile(r"<style[^>]*>(.*?)</style>", re.S)
DECL = re.compile(
    r"(?<![\w-])(min-height|height|min-width|width|position|content|gap|row-gap|column-gap|margin-top|margin-bottom|inset)\s*:\s*([^;]+)"
)
APPEARANCE = re.compile(r"(-?[a-z-]*appearance)\s*:\s*([^;]+)")
MIN_TOUCH = 48.0
MIN_GAP = 8.0


def _sources():
    for path in sorted(STATIC.glob("*.css")):
        yield str(path.relative_to(ROOT)), path.read_text(encoding="utf-8")
    for path in sorted(TEMPLATES.glob("*.html")):
        html = path.read_text(encoding="utf-8")
        for index, block in enumerate(STYLE_BLOCK.findall(html)):
            yield f"{path.relative_to(ROOT)}#style{index}", block


def _parse_rules(css):
    css = re.sub(r"/\*.*?\*/", "", css, flags=re.S)
    rules = []
    pos = 0
    while pos < len(css):
        brace = css.find("{", pos)
        if brace == -1:
            break
        header = css[pos:brace].strip()
        depth = 1
        end = brace + 1
        while end < len(css) and depth:
            if css[end] == "{":
                depth += 1
            elif css[end] == "}":
                depth -= 1
            end += 1
        body = css[brace + 1 : end - 1]
        if header.startswith("@"):
            rules.extend(_parse_rules(body))
        elif header:
            rules.append((header, body))
        pos = end
    return rules


def declarations(selector):
    found = []
    for source, css in _sources():
        for header, body in _parse_rules(css):
            for part in header.split(","):
                if " ".join(part.split()) == selector:
                    for prop, raw in DECL.findall(body):
                        found.append((source, prop.strip(), raw.strip()))
    return found


def px(value):
    value = value.strip().split()[0] if value.strip() else ""
    if value in ("var(--touch-min)", "var(--input-h)", "var(--tap-min)"):
        return MIN_TOUCH
    match = re.match(r"^(-?[\d.]+)px$", value)
    if match:
        return float(match.group(1))
    match = re.match(r"^(-?[\d.]+)rem$", value)
    if match:
        return float(match.group(1)) * 16
    return None


def appearance_declarations(selector):
    found = []
    for _source, css in _sources():
        for header, body in _parse_rules(css):
            for part in header.split(","):
                if " ".join(part.split()) == selector:
                    found.extend((p.strip(), v.strip()) for p, v in APPEARANCE.findall(body))
    return found


def first_px(selector, props):
    values = [
        px(raw)
        for _source, prop, raw in declarations(selector)
        if prop in props and px(raw) is not None
    ]
    return max(values) if values else None


T1_DIRECT = (
    ".btn",
    ".btn-sm",
    ".btn-secondary",
    ".ui-btn",
    ".ui-btn-compact",
    ".icon-btn",
    ".theme-switch .theme-seg",
    ".bell-wrap",
    ".collapse-btn",
    ".tab",
    ".dt-tab",
    ".back-link",
    ".group-btn",
    ".filter-chip-feed",
    ".filter-chip",
    ".more-details > summary",
    ".checkin-month",
    ".payout-cell",
    ".generate-btn",
    ".print-btn",
    ".settings-nav-item",
    ".search-input",
    ".search-page-input",
    ".search-option",
    ".search-hit",
    ".combobox-option",
    ".advanced-email summary",
    ".setup-guide summary",
    ".bottom-tab",
    ".sidebar nav a",
    ".field input",
    ".field select",
    '.move-form input[type="date"]',
    '.move-form input[type="text"]',
    '.move-form input[type="number"]',
    ".move-form select",
    ".alert-feed .alert-card",
    "a.chip",
    ".overflow-panel .privacy-toggle",
    ".check-row",
    ".field .checkbox-line",
    ".check-inline",
    ".share-checks label",
    ".share-format label",
    '.check-row input[type="checkbox"]',
    '.checkbox-line input[type="checkbox"]',
    '.check-inline input[type="checkbox"]',
    '.share-checks input[type="checkbox"]',
    '.share-format input[type="radio"]',
    '.field input[type="checkbox"]',
    ".payout-editor input[type=\"number\"]",
)

T2_GAPS = (
    (".topbar-actions", "gap"),
    (".sidebar nav", "gap"),
    (".detail-tabs", "gap"),
    (".checkin-strip", "gap"),
    (".settings-nav", "gap"),
    (".row-actions", "gap"),
    (".history-chips", "gap"),
    (".payout-editor", "gap"),
    (".check-inline", "gap"),
    (".share-checks", "gap"),
    (".share-format", "gap"),
    (".search-hit", "margin-bottom"),
    (".dd-actions", "gap"),
    (".guide-foot", "gap"),
    (".header-actions", "gap"),
    (".tabs", "gap"),
    (".filter-chips", "gap"),
    (".error-actions", "gap"),
    (".confirm-actions", "gap"),
    (".move-actions", "gap"),
    (".details-actions", "gap"),
    (".alert-feed .alert-card", "margin-top"),
    (".feed-toolbar", "gap"),
    (".group-by-row", "gap"),
    (".form-grid", "gap"),
)

T2_EXCEPTIONS = {
    ".theme-switch": "segmented control: adjacent segments are one logical radio group, shared border by design",
    ".bottom-tabs": "equal-width bottom navigation strip: contiguous tabs, each >=48px, no gap by design",
    ".payouts-table td": "dense data grid: adjacent payout cells are contiguous by design, each >=48px tall",
    ".tip-wrap": "inline help marker: hit area expanded with a transparent pseudo-element, not by a layout gap",
    ".about-link": "inline prose link: hit area expanded with a transparent pseudo-element",
    ".fetch-link": "inline prose link: hit area expanded with a transparent pseudo-element",
    ".caption-tap-link": "inline prose link: hit area expanded with a transparent pseudo-element, sentence visual unchanged",
}


def _client(db_path):
    app = create_app(str(db_path))
    app.config["TESTING"] = True
    return app.test_client()


@pytest.mark.skip(reason="Retired per issue #337: old frontend removal")
def test_t1_every_named_tappable_has_48px_box():
    undersized = []
    for selector in T1_DIRECT:
        height = first_px(selector, {"min-height", "height"})
        if height is None or height < MIN_TOUCH:
            undersized.append((selector, height))
    assert not undersized, undersized


@pytest.mark.skip(reason="Retired per issue #337: old frontend removal")
def test_t1_checkbox_hit_box_is_48_with_small_visual():
    for selector in (
        '.check-row input[type="checkbox"]',
        '.checkbox-line input[type="checkbox"]',
        '.check-inline input[type="checkbox"]',
        '.share-checks input[type="checkbox"]',
        '.share-format input[type="radio"]',
        '.field input[type="checkbox"]',
    ):
        decls = declarations(selector)
        assert any(prop in ("width", "min-width") and px(raw) == MIN_TOUCH for _s, prop, raw in decls), selector
        assert any(prop in ("height", "min-height") and px(raw) == MIN_TOUCH for _s, prop, raw in decls), selector
        assert any(value == "none" for _prop, value in appearance_declarations(selector)), selector
        visual = [
            px(raw)
            for _s, prop, raw in declarations(f"{selector}::before")
            if prop in ("width", "height") and px(raw) is not None
        ]
        assert visual and max(visual) < MIN_TOUCH, (selector, visual)


@pytest.mark.skip(reason="Retired per issue #337: old frontend removal")
def test_t1_small_icon_controls_use_transparent_hit_expansion():
    trigger = declarations(".tip-trigger")
    assert any(prop == "position" and raw == "relative" for _s, prop, raw in trigger)
    expansion = declarations(".tip-trigger::after")
    assert any(prop == "content" and raw.strip('"') == "" for _s, prop, raw in expansion)
    insets = [px(raw) for _s, prop, raw in expansion if prop == "inset" and px(raw) is not None]
    assert insets and abs(min(insets)) * 2 + px("1.35rem") >= MIN_TOUCH, insets
    for selector in (".about-link::after", ".fetch-link::after", ".caption-tap-link::after"):
        values = [px(raw) for _s, prop, raw in declarations(selector) if prop == "inset" and px(raw) is not None]
        assert values and abs(min(values)) * 2 + px("12px") * 1.5 >= MIN_TOUCH, (selector, values)


@pytest.mark.skip(reason="Retired per issue #337: old frontend removal")
def test_t1_round2_five_controls_extend_contract():
    for selector in (".filter-chip", ".filter-chip-feed"):
        width = first_px(selector, {"min-width", "width"})
        assert width is not None and width >= MIN_TOUCH, (selector, width)
    assert first_px(".more-details > summary", {"min-height"}) >= MIN_TOUCH
    caption = declarations(".caption-tap-link")
    assert any(prop == "position" and raw == "relative" for _s, prop, raw in caption)
    values = [
        px(raw)
        for _s, prop, raw in declarations(".caption-tap-link::after")
        if prop == "inset" and px(raw) is not None
    ]
    assert values and abs(min(values)) * 2 + px("12px") * 1.5 >= MIN_TOUCH, values
    alerts = (TEMPLATES / "notifications.html").read_text(encoding="utf-8")
    watch = (TEMPLATES / "watch.html").read_text(encoding="utf-8")
    assert 'class="caption-tap-link" href="/settings"' in alerts
    assert 'class="caption-tap-link" href="/goals"' in watch
    corridor = declarations(".caption-tap-corridor")
    for prop in ("margin-top", "margin-bottom"):
        vals = [px(raw) for _s, p, raw in corridor if p == prop and px(raw) is not None]
        assert vals and max(vals) >= px("1.75rem"), (prop, vals)
    assert 'class="caption caption-tap-corridor"' in watch


@pytest.mark.skip(reason="Retired per issue #337: old frontend removal")
def test_t2_neighbor_gaps_are_at_least_8px():
    narrow = []
    for selector, prop in T2_GAPS:
        value = first_px(selector, {prop})
        if value is None or value < MIN_GAP:
            narrow.append((selector, prop, value))
    assert not narrow, narrow


def test_t2_exceptions_are_documented_and_not_used_to_hide_offenders():
    assert all(T2_EXCEPTIONS.values())
    for selector in T2_EXCEPTIONS:
        assert selector not in T1_DIRECT, selector
    assert '.check-row input[type="checkbox"]' in T1_DIRECT
    assert ".bell-wrap" in T1_DIRECT
    assert ".ui-btn-compact" in T1_DIRECT


@pytest.mark.skip(reason="Retired per issue #337: old frontend removal")
def test_specific_charter3_bell_and_apply_are_fixed():
    bell = declarations(".bell-wrap")
    assert any(prop == "min-width" and px(raw) >= MIN_TOUCH for _s, prop, raw in bell)
    assert any(prop == "min-height" and px(raw) >= MIN_TOUCH for _s, prop, raw in bell)
    assert first_px(".ui-btn-compact", {"min-height"}) >= MIN_TOUCH
    assert first_px(".btn-sm", {"min-height"}) >= MIN_TOUCH
    assert (
        "role=\"button\"" in (TEMPLATES / "base.html").read_text(encoding="utf-8")
        and 'id="notificationsBell"' in (TEMPLATES / "base.html").read_text(encoding="utf-8")
    )


@pytest.mark.skip(reason="Retired per issue #337: old frontend removal")
def test_no_color_or_wording_changes_in_touch_rules():
    theme = (STATIC / "theme.css").read_text(encoding="utf-8")
    assert "--accent: #2563eb" in theme
    assert "--accent: #58a6ff" in theme
    assert "--on-accent: #ffffff" in theme
    assert "--on-accent: #0d1117" in theme
    assert 'content: "\\2713"' in theme


@pytest.mark.skip(reason="Retired per issue #337: old frontend removal")
def test_state_watch_form_and_move_panel_controls(db_path):
    with get_conn(db_path) as conn:
        add_bond(conn, "Touch Co", "INE303000001", "2026-01-05", 24)
        conn.execute("UPDATE bonds SET watch_state = 'watching' WHERE isin = 'INE303000001'")
    html = _client(db_path).get("/watch").get_data(as_text=True)
    for marker in (
        'id="fetch-details-apply"',
        'id="add-candidate-toggle"',
        "move-toggle",
        "move-cancel",
        "ui-btn-compact",
        'id="c-isin-fetch"',
    ):
        assert marker in html, marker


@pytest.mark.skip(reason="Retired per issue #337: old frontend removal")
def test_state_settings_toggles_use_touch_checked_rows(db_path):
    html = _client(db_path).get("/settings").get_data(as_text=True)
    for name in ("privacy_on_startup", "alert_inapp", "alert_email", "auto_fetch_enabled"):
        assert f'name="{name}"' in html
    assert html.count('class="check-row"') >= 4
    assert first_px(".check-row", {"min-height"}) >= MIN_TOUCH


@pytest.mark.skip(reason="Retired per issue #337: old frontend removal")
def test_state_alerts_bell_has_unread_badge_and_48px_rule(db_path):
    with get_conn(db_path) as conn:
        conn.execute(
            "INSERT INTO notifications (created_at, severity, message, read) VALUES (datetime('now'), 'danger', 'touch alert', 0)"
        )
    html = _client(db_path).get("/").get_data(as_text=True)
    assert 'id="notificationsBell"' in html
    assert 'id="unreadCount"' in html
    assert first_px(".bell-wrap", {"min-width", "min-height"}) >= MIN_TOUCH


def test_existing_fixed_px_guard_stays_green():
    sweep = __import__("test_layout_fixed_px_sweep", fromlist=["scanned_px_offsets"])
    offenders = [hit for hit in sweep.scanned_px_offsets() if hit not in sweep.ALLOWLIST]
    assert not offenders, offenders
