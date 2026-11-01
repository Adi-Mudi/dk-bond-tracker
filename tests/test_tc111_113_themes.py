import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.app import create_app

ROOT = Path(__file__).resolve().parents[1]
THEME_VALUES = ("system", "light", "dark")


def _seg_values(html):
    return re.findall(r'class="[^"]*theme-seg[^"]*" data-theme-value="([a-z]+)"', html)


def _radio_values(html):
    return re.findall(
        r'<input type="radio" name="theme-choice" data-theme-value="([a-z]+)"', html
    )


def test_tc113_header_has_three_theme_segments(db_path):
    app = create_app(str(db_path))
    html = app.test_client().get("/").get_data(as_text=True)
    values = _seg_values(html)
    assert tuple(values) == THEME_VALUES


def test_tc113_settings_has_same_three_radio_modes(db_path):
    app = create_app(str(db_path))
    html = app.test_client().get("/settings").get_data(as_text=True)
    values = _radio_values(html)
    assert tuple(values) == THEME_VALUES


def test_tc113_header_and_settings_stay_in_sync(db_path):
    app = create_app(str(db_path))
    client = app.test_client()
    home = client.get("/").get_data(as_text=True)
    settings = client.get("/settings").get_data(as_text=True)
    assert _seg_values(home) == _radio_values(settings)
    assert 'data-theme-value="system" checked' in settings
    js = (ROOT / "src" / "static" / "theme.js").read_text(encoding="utf-8")
    assert "themeSegments" in js and "themeRadios" in js


def test_tc111_boot_script_sets_theme_before_paint(db_path):
    app = create_app(str(db_path))
    html = app.test_client().get("/").get_data(as_text=True)
    assert "localStorage.getItem('dk-theme') || 'system'" in html
    assert "document.documentElement.setAttribute('data-theme'" in html
    assert "prefers-color-scheme: dark" in html
    assert "matchMedia" in html


def test_tc111_app_js_default_and_persist(db_path):
    js = (ROOT / "src" / "static" / "theme.js").read_text(encoding="utf-8")
    assert "localStorage.getItem('dk-theme') || 'system'" in js
    assert "localStorage.setItem('dk-theme'" in js
    assert "data-theme" in js
    app = create_app(str(db_path))
    client = app.test_client()
    assert client.get("/static/theme.js").status_code == 200


def test_tc111_dark_theme_block_exists_and_avoids_pure_black():
    css = (ROOT / "src" / "static" / "theme.css").read_text(encoding="utf-8")
    assert 'html[data-theme="dark"]' in css
    assert ':root, html[data-theme="light"]' in css
    assert 'html[data-theme="system"]' in css
    assert re.search(r"#000(?![0-9a-fA-F])", css) is None
    dark_block = css.split('html[data-theme="dark"] {', 1)[1].split("}", 1)[0]
    assert "--bg: #0d1117" in dark_block
    assert "--card: #161b22" in dark_block
