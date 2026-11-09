import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.app import create_app
from src.views.common import APP_VERSION, BUILD_NOTES


def test_tc99_about_shows_version_build_notes_offline_badge(db_path):
    app = create_app(str(db_path))
    client = app.test_client()
    html = client.get("/about").get_data(as_text=True)
    assert 'id="about-app-card"' in html
    assert f"Version {APP_VERSION}" in html
    assert 'id="app-version"' in html
    assert BUILD_NOTES in html
    assert 'id="build-notes-line"' in html
    assert "100% offline — no accounts, no cloud" in html
    assert 'id="offline-badge"' in html


def test_tc99_reveal_button_and_hidden_data_dir(db_path):
    app = create_app(str(db_path))
    client = app.test_client()
    html = client.get("/about").get_data(as_text=True)
    assert 'id="reveal-data-folder"' in html
    assert 'id="data-dir-wrap" hidden' in html
    assert 'id="data-dir-path"' in html
    assert str(db_path.parent) in html
    assert "reveal-data-folder" in html
    assert "wrap.hidden = false" in html


def test_tc99_settings_no_longer_inlines_about(db_path):
    app = create_app(str(db_path))
    client = app.test_client()
    html = client.get("/settings").get_data(as_text=True)
    assert 'id="about-card"' not in html
    assert 'id="section-about"' not in html
    assert 'id="nav-about"' in html
    assert 'href="/about"' in html


def test_tc99_settings_error_render_stays_on_settings(db_path):
    app = create_app(str(db_path))
    client = app.test_client()
    response = client.post(
        "/settings",
        data={"smtp_host": "smtp.example.com", "smtp_port": "not-a-port"},
    )
    assert response.status_code == 400
    html = response.get_data(as_text=True)
    assert "ERR-settings-save" in html
    assert 'id="settings-error"' in html
    assert 'id="about-card"' not in html
