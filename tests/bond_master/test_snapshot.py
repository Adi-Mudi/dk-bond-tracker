from src.bond_master import snapshot
from src.bond_master.base import INSTRUMENT_FIELDS, SOURCE_PRIORITY
from src.bond_master.cache import BondMasterCache
from src.bond_master.service import BondMasterService

SNAPSHOT_ISIN = "IN8020B08012"


class OfflineAdapter:
    def __init__(self, name):
        self.name = name

    def fetch(self, isin):
        raise OSError("offline")


def test_snapshot_is_a_committed_cc0_dataset():
    assert snapshot.SNAPSHOT_PATH.exists()
    assert snapshot.SNAPSHOT_LICENSE == "CC0-1.0"
    assert snapshot.SNAPSHOT_SOURCE == "india-isin-data (CC0)"
    assert snapshot.version()
    assert snapshot.rows()


def test_snapshot_rows_only_carry_af01_fields_the_dataset_has():
    row = snapshot.rows()[SNAPSHOT_ISIN]
    assert set(row) <= set(INSTRUMENT_FIELDS)
    assert row["company"] == "REC LIMITED"
    assert "rating" not in row
    assert "rating_agency" not in row


def test_snapshot_lookup_labels_every_field_with_the_source():
    result = snapshot.snapshot_lookup(SNAPSHOT_ISIN)
    assert result is not None
    assert result.has_facts() is True
    for field in result.sources:
        assert result.source_of(field) == snapshot.SNAPSHOT_SOURCE


def test_snapshot_lookup_ignores_an_unknown_isin():
    assert snapshot.snapshot_lookup("INE205A07DV2") is None
    assert snapshot.snapshot_lookup("not-an-isin") is None
    assert snapshot.contains(SNAPSHOT_ISIN) is True


def test_af11_2_fresh_db_snapshot_answers_a_common_isin_offline(tmp_path):
    adapters = {name: OfflineAdapter(name) for name in SOURCE_PRIORITY}
    service = BondMasterService(
        adapters,
        BondMasterCache(tmp_path / "bonds.db"),
        sleep=lambda _delay: None,
        throttle_seconds=0.0,
        retries=0,
    )
    result = service.lookup(SNAPSHOT_ISIN)
    assert result.has_facts() is True
    assert result.company == "REC LIMITED"
    assert result.source_of("company") == snapshot.SNAPSHOT_SOURCE


def test_snapshot_never_answers_an_isin_it_does_not_hold(tmp_path):
    adapters = {name: OfflineAdapter(name) for name in SOURCE_PRIORITY}
    service = BondMasterService(
        adapters,
        BondMasterCache(tmp_path / "bonds.db"),
        sleep=lambda _delay: None,
        throttle_seconds=0.0,
        retries=0,
    )
    result = service.lookup("INE205A07DV2")
    assert result.has_facts() is False
    assert result.failure_code == "OFFLINE"
