from pathlib import Path

import pytest

from src.app import create_app

TEMPLATES = Path("src/templates")


@pytest.fixture
def client(db_path):
    app = create_app(str(db_path))
    app.config["TESTING"] = True
    return app.test_client()


def test_logo_paths_only_in_brand_partial():
    offenders = []
    for path in TEMPLATES.rglob("*.html"):
        if path.name == "_brand.html":
            continue
        text = path.read_text(encoding="utf-8")
        for token in ("/static/img/logo/", "apple-touch-icon", 'rel="manifest"'):
            if token in text:
                offenders.append(f"{path.name}: contains {token}")
    assert offenders == [], offenders


def test_pages_import_brand_macros():
    base = (TEMPLATES / "base.html").read_text(encoding="utf-8")
    about = (TEMPLATES / "about.html").read_text(encoding="utf-8")
    assert 'import brand_head, brand_mark, brand_avatar' in base
    assert "{{ brand_head() }}" in base
    assert "{{ brand_mark(24) }}" in base
    assert "brand_avatar" in about


def test_rendered_pages_still_carry_logo(client):
    home = client.get("/").get_data(as_text=True)
    assert "/static/img/logo/favicon.svg?v=2" in home
    assert "/static/img/logo/logo-mark.svg?v=2" in home
    about = client.get("/about").get_data(as_text=True)
    assert "/static/img/logo/logo-512.png?v=2" in about
