import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
THEME = (ROOT / "src" / "static" / "theme.css").read_text(encoding="utf-8")
PRINT = (ROOT / "src" / "templates" / "monthly_print.html").read_text(encoding="utf-8")
SETTINGS = (ROOT / "src" / "templates" / "settings.html").read_text(encoding="utf-8")
GRID = (ROOT / "src" / "templates" / "grid.html").read_text(encoding="utf-8")


def test_tc147_dead_blue_token_removed():
    assert not re.search(r"--blue:\s*#", THEME)
    assert "--blue-light:" in THEME


def test_tc147_btn_hover_restores_text_color():
    assert ".btn:hover { background: var(--bg); color: var(--text); }" in THEME


def test_tc147_notification_header_uses_theme_tokens():
    block = THEME[THEME.index(".alert-dropdown-v3 .dd-head"):]
    block = block[: block.index("}")]
    assert "background: var(--bar-muted)" in block
    assert "color: var(--text)" in block
    assert not re.search(r"#[0-9a-fA-F]{3,6}", block)


def test_tc147_print_declares_only_used_tokens():
    for token in ("--danger:", "--ongoing:", "--completed:", "--page-bg:"):
        assert token not in PRINT
    assert "box-shadow: 0 6px 24px var(--shadow-overlay)" in PRINT


def test_tc147_theme_init_has_one_inline_bootstrap_only():
    assert "forEach(function(r){r.checked" not in SETTINGS
    assert "theme-seg" not in SETTINGS


def test_tc147_grid_legend_copy_matches_current_colors():
    assert "light red" not in GRID
    assert "tinted red" in GRID
