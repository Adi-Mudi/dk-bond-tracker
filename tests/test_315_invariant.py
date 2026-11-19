import json

import pytest

from src.bond_master.base import SOURCE_PRIORITY, FetchResult
from src.bond_master.service import BondMasterService
from src.bond_master.snapshot import SNAPSHOT_PATH, SNAPSHOT_SOURCE

OFFICIAL_FIELDS = ("rating", "rating_agency", "issuer_type", "payout_cycle", "secured")
OFFICIAL_VALUES = {
    "rating": "AA",
    "rating_agency": "CARE",
    "issuer_type": "ncd",
    "payout_cycle": "annual",
    "secured": 1,
}


class _MemoryCache:
    def __init__(self):
        self._sessions = {}

    def begin_refresh(self):
        return 0.0

    def session_result(self, source, isin):
        return self._sessions.get((source, isin))

    def fetch_session(self, source, isin, fetcher):
        key = (source, isin)
        if key not in self._sessions:
            self._sessions[key] = fetcher()
        return self._sessions[key]

    def lookup(self, isin):
        return None


class _OfficialAdapter:
    def __init__(self, name):
        self.name = name
        self.calls = 0

    def fetch(self, isin):
        self.calls += 1
        return FetchResult(
            isin=isin,
            sources={field: self.name for field in OFFICIAL_FIELDS},
            **OFFICIAL_VALUES,
        )


@pytest.mark.parametrize("official_source", SOURCE_PRIORITY)
def test_lookup_includes_official_facts_for_every_snapshot_isin(official_source):
    document = json.loads(SNAPSHOT_PATH.read_text(encoding="utf-8"))
    isins = tuple(document["rows"])
    assert isins
    adapter = _OfficialAdapter(official_source)
    service = BondMasterService(
        {official_source: adapter},
        _MemoryCache(),
        sleep=lambda _delay: None,
        throttle_seconds=0.0,
        retries=0,
    )
    for isin in isins:
        result = service.lookup(isin)
        assert result is not None, isin
        for field in OFFICIAL_FIELDS:
            assert getattr(result, field) == OFFICIAL_VALUES[field], f"{isin} {field} value"
            assert result.source_of(field) == official_source, f"{isin} {field} source"
        assert result.source_of("company") == SNAPSHOT_SOURCE, isin
    assert adapter.calls == len(isins)
