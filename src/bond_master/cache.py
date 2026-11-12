import time
from datetime import datetime, timezone
from pathlib import Path

from ..db import get_conn
from ..validators import AppError

COOLDOWN_SECONDS = 60

BOND_MASTER_FIELDS = (
    "isin",
    "company",
    "coupon",
    "payout_cycle",
    "face_value",
    "rating",
    "rating_agency",
    "issuer_type",
    "secured",
    "listing_status",
    "maturity",
    "source",
    "fetched_at",
)

_COLUMNS = ", ".join(BOND_MASTER_FIELDS)
_PLACEHOLDERS = ", ".join("?" for _ in BOND_MASTER_FIELDS)
_UPSERT = ", ".join(f"{field} = excluded.{field}" for field in BOND_MASTER_FIELDS if field != "isin")
_INSERT_SQL = (
    f"INSERT INTO bond_master ({_COLUMNS}) VALUES ({_PLACEHOLDERS}) "
    f"ON CONFLICT(isin) DO UPDATE SET {_UPSERT}"
)
_SELECT_SQL = f"SELECT {_COLUMNS} FROM bond_master WHERE isin = ?"


class CooldownActive(AppError):
    def __init__(self, remaining):
        super().__init__(
            "ERR-bond-master-cooldown",
            f"refresh blocked by the {COOLDOWN_SECONDS}s cooldown: {remaining:.1f}s remaining",
        )
        self.remaining = remaining


def _asof_timestamp(epoch_seconds):
    return datetime.fromtimestamp(epoch_seconds, tz=timezone.utc).isoformat(timespec="seconds")


class BondMasterCache:
    def __init__(self, db_path, clock=None, cooldown_seconds=COOLDOWN_SECONDS):
        self.db_path = Path(db_path)
        self._clock = clock or time.time
        self.cooldown_seconds = cooldown_seconds
        self._last_refresh_at = None
        self._session_results = {}
        self._edited_fields = {}

    def cooldown_remaining(self):
        if self._last_refresh_at is None:
            return 0.0
        elapsed = self._clock() - self._last_refresh_at
        return max(0.0, self.cooldown_seconds - elapsed)

    def refresh_allowed(self):
        return self.cooldown_remaining() <= 0.0

    def begin_refresh(self):
        remaining = self.cooldown_remaining()
        if remaining > 0.0:
            raise CooldownActive(remaining)
        self._last_refresh_at = self._clock()
        return self._last_refresh_at

    def session_result(self, source, isin):
        return self._session_results.get((source, isin))

    def fetch_session(self, source, isin, fetcher):
        key = (source, isin)
        if key not in self._session_results:
            self._session_results[key] = fetcher()
        return self._session_results[key]

    def mark_edited(self, isin, *fields):
        bucket = self._edited_fields.setdefault(isin, set())
        for field in fields:
            if field in BOND_MASTER_FIELDS and field != "isin":
                bucket.add(field)
        return frozenset(bucket)

    def edited_fields(self, isin):
        return frozenset(self._edited_fields.get(isin, ()))

    def save(self, record):
        values = {field: record.get(field) for field in BOND_MASTER_FIELDS}
        isin = values["isin"]
        if not isin:
            raise AppError("ERR-bond-master-isin", "bond_master row requires an isin")
        edited = self._edited_fields.get(isin)
        if edited:
            existing = self.lookup(isin)
            if existing is not None:
                for field in edited:
                    values[field] = existing[field]
        if values["fetched_at"] is None:
            values["fetched_at"] = _asof_timestamp(self._clock())
        with get_conn(self.db_path) as conn:
            conn.execute(_INSERT_SQL, tuple(values[field] for field in BOND_MASTER_FIELDS))
        return values

    def lookup(self, isin):
        with get_conn(self.db_path) as conn:
            row = conn.execute(_SELECT_SQL, (isin,)).fetchone()
        return None if row is None else {field: row[field] for field in BOND_MASTER_FIELDS}

    def as_of(self, isin):
        row = self.lookup(isin)
        return None if row is None else row["fetched_at"]

    def offer(self, isin):
        row = self.lookup(isin)
        if row is None:
            return None
        return {**row, "as_of": row["fetched_at"]}
