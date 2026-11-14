from __future__ import annotations

import json
from pathlib import Path

from .base import INSTRUMENT_FIELDS, FetchResult
from .normalize import normalize_isin

SNAPSHOT_NAME = "india-isin-data"
SNAPSHOT_SOURCE = "india-isin-data (CC0)"
SNAPSHOT_LICENSE = "CC0-1.0"
SNAPSHOT_PATH = Path(__file__).resolve().parent / "data" / "india_isin_snapshot.json"

_document = None


def _load():
    global _document
    if _document is None:
        try:
            with SNAPSHOT_PATH.open(encoding="utf-8") as handle:
                loaded = json.load(handle)
        except (OSError, ValueError):
            loaded = {}
        if not isinstance(loaded, dict):
            loaded = {}
        _document = loaded
    return _document


def reset():
    global _document
    _document = None


def document():
    return _load()


def version():
    value = _load().get("version")
    return value if isinstance(value, str) else None


def url():
    value = _load().get("url")
    return value if isinstance(value, str) else None


def rows():
    value = _load().get("rows")
    return value if isinstance(value, dict) else {}


def contains(isin):
    normalized = normalize_isin(isin)
    return False if normalized is None else normalized in rows()


def snapshot_lookup(isin):
    normalized = normalize_isin(isin)
    if normalized is None:
        return None
    row = rows().get(normalized)
    if not row:
        return None
    fields = {
        name: row[name]
        for name in INSTRUMENT_FIELDS
        if isinstance(row, dict) and row.get(name) is not None
    }
    if not fields:
        return None
    return FetchResult(
        isin=normalized,
        sources={name: SNAPSHOT_SOURCE for name in fields},
        **fields,
    )
