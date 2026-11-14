from pathlib import Path

from src.app import create_app
from src.bond_master import snapshot

SNAPSHOT_ISIN = "IN8020B08012"
SNAPSHOT_COMPANY = "REC LIMITED"


def make_client(db_path):
    app = create_app(str(db_path))
    app.config["TESTING"] = True
    return app.test_client(), app


def test_af11_2_fresh_install_answers_a_common_isin_with_no_network(db_path):
    def transport(url, timeout):
        raise FileNotFoundError("no local download configured")

    client, app = make_client(db_path)
    app.config["BOND_MASTER_TRANSPORT"] = transport
    html = client.get(f"/watch?isin={SNAPSHOT_ISIN}").get_data(as_text=True)
    assert f'value="{SNAPSHOT_COMPANY}"' in html
    assert 'data-fetch-source="company">india-isin-data (CC0)<' in html


def test_snapshot_module_never_imports_a_network_library():
    source = Path(snapshot.__file__).read_text(encoding="utf-8")
    for token in ("urllib", "socket", "requests", "http.client"):
        assert token not in source, token


def test_snapshot_lookup_needs_no_network(monkeypatch):
    import socket

    def blocked(*args, **kwargs):
        raise AssertionError("the snapshot must never open a socket")

    monkeypatch.setattr(socket, "socket", blocked)
    result = snapshot.snapshot_lookup(SNAPSHOT_ISIN)
    assert result is not None
    assert result.company == SNAPSHOT_COMPANY
