import pytest
pytest.skip("Retired per issue #337: old frontend removal", allow_module_level=True)
import re

from src.app import create_app
from src.bond_master.service import AUTO_FETCH_ENABLED_KEY, AUTO_FETCH_PROMPTED_KEY
from src.db import get_conn, init_db
from src.prefs import get_pref


def _client(db_path):
    app = create_app(str(db_path))
    app.config["TESTING"] = True
    return app.test_client()


def _pref(db_path, key):
    with get_conn(db_path) as conn:
        return get_pref(conn, key)


def _backdrop_css(html):
    match = re.search(r"\.update-popup-backdrop\s*\{([^}]*)\}", html)
    assert match, "consent backdrop CSS rule missing from first paint"
    return match.group(1)


def test_302_a_fresh_install_dialog_has_full_viewport_bounds(db_path):
    page = _client(db_path).get("/")
    assert page.status_code == 200
    html = page.get_data(as_text=True)

    assert 'id="auto-fetch-consent"' in html
    assert 'class="update-popup-backdrop" id="auto-fetch-consent"' in html
    assert 'data-auto-fetch-choice="later"' in html
    assert 'data-auto-fetch-choice="auto"' in html

    assert 'id="update-popup"' not in html

    css = _backdrop_css(html)
    assert "position: fixed" in css
    assert "inset: 0" in css
    assert html.index(".update-popup-backdrop") < html.index('id="auto-fetch-consent"')


def test_302_b_after_choice_dialog_gone_on_reload_and_after_relaunch(db_path):
    http = _client(db_path)
    assert b'id="auto-fetch-consent"' in http.get("/").data

    assert http.post("/settings/auto-fetch/consent", data={"choice": "later"}).status_code == 200
    assert b'id="auto-fetch-consent"' not in http.get("/").data

    relaunched = _client(db_path)
    assert b'id="auto-fetch-consent"' not in relaunched.get("/").data
    assert _pref(db_path, AUTO_FETCH_PROMPTED_KEY) == "1"
    assert _pref(db_path, AUTO_FETCH_ENABLED_KEY) == "0"


def test_302_c_settings_toggle_off_to_on_survives_relaunch_without_second_dialog(db_path):
    http = _client(db_path)
    http.post("/settings/auto-fetch/consent", data={"choice": "later"})
    assert 'name="auto_fetch_enabled"' in http.get("/settings?section=data").get_data(as_text=True)

    http.post("/settings?section=data", data={"section": "data", "auto_fetch_enabled": "1"})
    assert _pref(db_path, AUTO_FETCH_ENABLED_KEY) == "1"

    relaunched = _client(db_path)
    assert b'id="auto-fetch-consent"' not in relaunched.get("/").data
    settings = relaunched.get("/settings?section=data").get_data(as_text=True)
    assert 'name="auto_fetch_enabled" value="1" checked' in settings


def test_302_d_auto_choice_sets_prompted_and_enabled(db_path):
    http = _client(db_path)
    assert http.post("/settings/auto-fetch/consent", data={"choice": "auto"}).status_code == 200
    assert _pref(db_path, AUTO_FETCH_PROMPTED_KEY) == "1"
    assert _pref(db_path, AUTO_FETCH_ENABLED_KEY) == "1"
    assert b'id="auto-fetch-consent"' not in _client(db_path).get("/").data


def test_302_state_matrix_four_states(tmp_path):
    def new_db(name):
        path = tmp_path / name
        init_db(path)
        return path

    def shows_dialog(db_path):
        return b'id="auto-fetch-consent"' in _client(db_path).get("/").data

    fresh_db = new_db("fresh.db")
    fresh = shows_dialog(fresh_db)

    accept_db = new_db("accept.db")
    _client(accept_db).post("/settings/auto-fetch/consent", data={"choice": "auto"})
    relaunch_after_accept = shows_dialog(accept_db)

    decline_db = new_db("decline.db")
    _client(decline_db).post("/settings/auto-fetch/consent", data={"choice": "later"})
    relaunch_after_decline = shows_dialog(decline_db)

    settings_db = new_db("settings.db")
    toggler = _client(settings_db)
    toggler.post("/settings/auto-fetch/consent", data={"choice": "later"})
    toggler.post("/settings?section=data", data={"section": "data", "auto_fetch_enabled": "1"})
    settings_toggled = shows_dialog(settings_db)

    assert {
        "fresh_install": fresh,
        "relaunch_after_accept": relaunch_after_accept,
        "relaunch_after_decline": relaunch_after_decline,
        "settings_toggled": settings_toggled,
    } == {
        "fresh_install": True,
        "relaunch_after_accept": False,
        "relaunch_after_decline": False,
        "settings_toggled": False,
    }
