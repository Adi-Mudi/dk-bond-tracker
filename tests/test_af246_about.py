from src.app import create_app
from src.bond_master import snapshot
from src.views.about import DATA_SOURCES

SOURCE_NAMES = ("NSDL", "RBI", "NSE", "BSE", "india-isin-data")


def make_client(db_path):
    app = create_app(str(db_path))
    app.config["TESTING"] = True
    return app.test_client(), app


def test_af11_1_data_sources_name_the_five_sources():
    assert [item["name"] for item in DATA_SOURCES] == list(SOURCE_NAMES)


def test_af11_1_about_names_every_source_with_its_licence(db_path):
    client, _ = make_client(db_path)
    html = client.get("/about").get_data(as_text=True)
    for key in ("nsdl", "rbi", "nse", "bse", "india-isin-data"):
        assert f'id="data-source-{key}"' in html, key
    assert "CC0-1.0" in html or "CC0" in html
    assert snapshot.url() in html
    assert "Terms of Use" in html


def test_af11_1_about_shows_the_bundled_snapshot_version(db_path):
    client, _ = make_client(db_path)
    html = client.get("/about").get_data(as_text=True)
    assert f"v{snapshot.version()}" in html
