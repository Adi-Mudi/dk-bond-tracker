import re

import pytest

from src.app import create_app
from src.db import get_conn
from src.prefs import get_pref

SECTIONS = ("general", "notifications", "share", "data", "about")


@pytest.fixture
def client(db_path):
    app = create_app(str(db_path))
    app.config["TESTING"] = True
    return app.test_client()


def section_tag(html, key):
    match = re.search(
        r'<section class="settings-section" id="section-%s"([^>]*)>' % key, html
    )
    assert match, f"settings section missing: {key}"
    return match.group(1)


def hidden_sections(html):
    return {key for key in SECTIONS if "hidden" in section_tag(html, key)}


def active_nav(html):
    match = re.search(
        r'<a class="[^"]*settings-nav-item[^"]*active[^"]*" id="nav-(\w+)"', html
    )
    return match.group(1) if match else None


def test_ui07_subnav_renders_all_sections_and_marks_active(client, db_path):
    html = client.get("/settings").get_data(as_text=True)
    assert 'id="settings-nav"' in html
    for key in SECTIONS:
        assert f'id="nav-{key}"' in html
        assert f'id="section-{key}"' in html
    assert hidden_sections(html) == {"notifications", "share", "data", "about"}
    assert active_nav(html) == "general"


@pytest.mark.parametrize("key", SECTIONS)
def test_ui07_subnav_switches_active_section(client, db_path, key):
    html = client.get(f"/settings?section={key}").get_data(as_text=True)
    hidden = hidden_sections(html)
    assert key not in hidden
    assert len(hidden) == len(SECTIONS) - 1
    assert active_nav(html) == key


def test_ui07_deep_link_anchors_present_and_resolve(client, db_path):
    html = client.get("/settings").get_data(as_text=True)
    for key in SECTIONS:
        assert f'href="/settings?section={key}#section-{key}"' in html
    deep = client.get("/settings?section=data#section-data").get_data(as_text=True)
    assert "hidden" not in section_tag(deep, "data")
    assert active_nav(deep) == "data"


def test_ui07_unknown_section_falls_back_to_general(client, db_path):
    html = client.get("/settings?section=bogus").get_data(as_text=True)
    assert active_nav(html) == "general"


def test_ui07_advanced_email_is_collapsed_by_default(client, db_path):
    html = client.get("/settings").get_data(as_text=True)
    match = re.search(r"<details([^>]*)id=\"advanced-email\"([^>]*)>", html)
    assert match, "advanced email panel missing"
    assert "open" not in (match.group(1) + match.group(2))
    assert "Advanced &#8212; Email (SMTP)" in html
    assert html.index('name="smtp_host"') > html.index('id="advanced-email"')
    assert html.index('id="s-send-test"') > html.index('id="advanced-email"')
    assert html.index('id="email-setup-guide"') > html.index('id="advanced-email"')


def test_ui07_no_appearance_radio_and_single_theme_home(client, db_path):
    html = client.get("/settings").get_data(as_text=True)
    assert 'name="theme-choice"' not in html
    assert 'type="radio"' not in html
    assert 'id="appearance-card"' not in html
    assert 'id="theme-pointer"' in html
    assert "top-bar overflow icon" in html


def test_ui07_saved_feedback_appears_after_save(client, db_path):
    before = client.get("/settings").get_data(as_text=True)
    assert 'id="settings-saved" hidden' in before
    response = client.post(
        "/settings",
        data={"section": "general", "smtp_host": "smtp.example.com", "smtp_port": "587"},
        follow_redirects=True,
    )
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert 'id="settings-saved"' in html
    assert 'id="settings-saved" hidden' not in html
    assert "&#10003; Saved" in html
    assert 'id="settings-dirty" hidden' in html


def test_ui07_save_redirects_back_to_the_same_section(client, db_path):
    response = client.post(
        "/settings", data={"section": "share"}, follow_redirects=False
    )
    assert response.status_code == 302
    assert response.headers["Location"].startswith("/settings?section=share")
    assert "saved=1" in response.headers["Location"]


def test_ui07_notifications_config_reachable_and_persisted(client, db_path):
    html = client.get("/settings?section=notifications").get_data(as_text=True)
    assert 'id="settings-alert-channels"' in html
    assert 'name="alert_inapp"' in html
    assert 'name="alert_email"' in html
    assert 'id="settings-day-wise-rules"' in html
    assert "status becomes Danger same day" in html

    response = client.post(
        "/settings",
        data={"section": "notifications", "alert_inapp": "on", "alert_email": "on"},
        follow_redirects=False,
    )
    assert response.status_code == 302
    with get_conn(db_path) as conn:
        assert get_pref(conn, "alert_channel_inapp") == "1"
        assert get_pref(conn, "alert_channel_email") == "1"

    client.post("/settings", data={"section": "notifications"}, follow_redirects=False)
    with get_conn(db_path) as conn:
        assert get_pref(conn, "alert_channel_inapp") == "0"
        assert get_pref(conn, "alert_channel_email") == "0"


def test_ui07_sticky_subnav_on_desktop(client, db_path):
    html = client.get("/settings").get_data(as_text=True)
    assert "position: sticky" in html
    assert ".settings-nav" in html
    assert "@media (max-width: 768px)" in html


def test_ui07_about_section_keeps_about_content(client, db_path):
    html = client.get("/settings?section=about").get_data(as_text=True)
    assert 'id="about-card"' in html
    assert 'id="app-version"' in html
    assert 'id="offline-badge"' in html
    assert 'id="reveal-data-folder"' in html
    assert 'id="data-dir-wrap" hidden' in html


def test_ui07_settings_error_keeps_section_and_about(client, db_path):
    response = client.post(
        "/settings",
        data={"section": "general", "smtp_host": "smtp.example.com", "smtp_port": "nope"},
        follow_redirects=False,
    )
    assert response.status_code == 400
    html = response.get_data(as_text=True)
    assert "ERR-settings-save" in html
    assert 'id="about-card"' in html
    assert active_nav(html) == "general"
