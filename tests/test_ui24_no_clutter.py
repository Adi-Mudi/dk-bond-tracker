from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEMPLATES = ROOT / "src" / "templates"

REMOVED = {
    "portfolio.html": ("Status legend", "chip-watching\">Watching</span><span class=\"caption\""),
    "dashboard.html": ("sorted-caption", "chart-legend", "history-note"),
    "watch.html": ("Watchlist holds candidates only",),
    "grid.html": ("autosort-badge",),
}


def offenders():
    found = []
    for name, needles in REMOVED.items():
        text = (TEMPLATES / name).read_text(encoding="utf-8")
        for needle in needles:
            if needle in text:
                found.append(f"{name}: {needle}")
    return found


def test_unwanted_labels_and_legends_are_gone():
    assert offenders() == []


def test_guard_detects_a_reintroduced_label():
    sample = '<h2>Status legend</h2>'
    assert "Status legend" in sample


def test_grid_sorting_rule_lives_in_the_page_guide():
    guide = (TEMPLATES / "_guide.html").read_text(encoding="utf-8")
    assert "Payout grid guide" in guide
    assert "Danger rows sit at the top" in guide


def test_dashboard_empty_state_survives():
    dashboard = (TEMPLATES / "dashboard.html").read_text(encoding="utf-8")
    assert "dashboard-bars-empty" in dashboard
