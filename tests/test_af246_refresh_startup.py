import src.app as app_module
from src.app import create_app


def test_af10_1_app_start_triggers_one_background_auto_refresh(db_path, monkeypatch):
    calls = []
    monkeypatch.setattr(
        app_module,
        "refresh_all",
        lambda db, trigger="manual", transport=None: calls.append(trigger),
    )
    monkeypatch.setattr(app_module, "_auto_refresh_started", False)

    first = create_app(str(db_path))
    thread = first.extensions.get("bond_master_auto_refresh")
    if thread is not None:
        thread.join(timeout=5)

    second = create_app(str(db_path))
    thread = second.extensions.get("bond_master_auto_refresh")
    if thread is not None:
        thread.join(timeout=5)

    assert calls == ["auto"]


def test_af10_startup_records_the_snapshot_version_flag(db_path):
    from src.bond_master import snapshot
    from src.db import get_conn
    from src.prefs import get_snapshot_version

    create_app(str(db_path))
    with get_conn(db_path) as conn:
        assert get_snapshot_version(conn) == snapshot.version()
