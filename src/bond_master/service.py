from __future__ import annotations

import threading
import time
from pathlib import Path

from .base import (
    FAILURE_BLOCKED,
    FAILURE_INVALID_ISIN,
    FAILURE_MALFORMED,
    FAILURE_NOT_FOUND,
    FAILURE_OFFLINE,
    FAILURE_OK,
    FAILURE_PARSE_ERROR,
    FAILURE_RATE_LIMITED,
    FAILURE_TIMEOUT,
    FAILURE_UNREACHABLE,
    INSTRUMENT_FIELDS,
    SOURCE_PRIORITY,
    FetchResult,
)
from .cache import BondMasterCache, CooldownActive
from .health import SourceEvent, health_view
from .normalize import normalize_isin, split_rating
from .snapshot import SNAPSHOT_SOURCE, snapshot_lookup

DEFAULT_RETRIES = 2
DEFAULT_RETRY_BACKOFF = 0.5
DEFAULT_THROTTLE_SECONDS = 1.0
DEFAULT_TIMEOUT = 10.0

_RETRYABLE = (FAILURE_UNREACHABLE, FAILURE_TIMEOUT)

_FAILURE_PRIORITY = (
    FAILURE_TIMEOUT,
    FAILURE_UNREACHABLE,
    FAILURE_BLOCKED,
    FAILURE_RATE_LIMITED,
    FAILURE_PARSE_ERROR,
    FAILURE_MALFORMED,
    FAILURE_NOT_FOUND,
    FAILURE_OFFLINE,
    FAILURE_INVALID_ISIN,
    FAILURE_OK,
)

_SOURCE_STATUS = {
    FAILURE_OK: "ok",
    FAILURE_NOT_FOUND: "not_found",
    FAILURE_UNREACHABLE: "offline",
    FAILURE_OFFLINE: "offline",
    FAILURE_TIMEOUT: "timeout",
    FAILURE_BLOCKED: "blocked",
    FAILURE_MALFORMED: "malformed",
    FAILURE_PARSE_ERROR: "parse_error",
    FAILURE_RATE_LIMITED: "rate_limited",
    FAILURE_INVALID_ISIN: "invalid_isin",
}

_ADAPTER_CLASS = {
    "NSDL": "NsdlAdapter",
    "RBI": "RbiAdapter",
    "NSE": "NseAdapter",
    "BSE": "BseAdapter",
}

_CACHES = {}
_AUTO_REFRESH_DONE = False
_CACHE_LOCK = threading.Lock()
_AUTO_LOCK = threading.Lock()


def _dominant_failure(codes):
    for code in _FAILURE_PRIORITY:
        if code in codes:
            return code
    return FAILURE_NOT_FOUND


def _empty_code(failure_code):
    return FAILURE_NOT_FOUND if failure_code == FAILURE_OK else failure_code


def _absorb(values, sources, source, result):
    for field in INSTRUMENT_FIELDS:
        if field in values:
            continue
        value = getattr(result, field)
        if value is None:
            continue
        values[field] = value
        sources[field] = result.source_of(field) or source


def _clean_rating(values, sources):
    if "rating" not in values and "rating_agency" not in values:
        return
    grade, agency = split_rating(values.get("rating"), values.get("rating_agency"))
    if grade is None:
        values.pop("rating", None)
        sources.pop("rating", None)
    else:
        values["rating"] = grade
    if agency is None:
        values.pop("rating_agency", None)
        sources.pop("rating_agency", None)
    else:
        values["rating_agency"] = agency
        if "rating_agency" not in sources:
            sources["rating_agency"] = sources.get("rating")


def _merged_result(isin, values, sources):
    _clean_rating(values, sources)
    return FetchResult(isin=isin, sources=sources, **values)


def primary_source(sources):
    names = {name for name in (sources or {}).values() if name}
    for source in SOURCE_PRIORITY:
        if source in names:
            return source
    return sorted(names)[0] if names else None


def _bond_record(result):
    record = {"isin": result.isin, "source": primary_source(result.sources)}
    record.update(result.facts())
    return record


def _cache_key(db_path):
    return str(Path(db_path).resolve())


def shared_cache(db_path):
    key = _cache_key(db_path)
    with _CACHE_LOCK:
        cache = _CACHES.get(key)
        if cache is None:
            cache = BondMasterCache(key)
            _CACHES[key] = cache
        return cache


def _claim_auto(db_path):
    global _AUTO_REFRESH_DONE
    with _AUTO_LOCK:
        if _AUTO_REFRESH_DONE:
            return False
        _AUTO_REFRESH_DONE = True
        return True


def _known_isins(db_path):
    from ..db import get_conn

    try:
        with get_conn(db_path) as conn:
            rows = conn.execute(
                "SELECT DISTINCT isin FROM bond_master WHERE isin IS NOT NULL"
            ).fetchall()
    except Exception:
        return []
    return [row["isin"] for row in rows]


class BondMasterService:
    def __init__(
        self,
        adapters,
        cache,
        clock=None,
        sleep=None,
        retries=DEFAULT_RETRIES,
        retry_backoff=DEFAULT_RETRY_BACKOFF,
        throttle_seconds=DEFAULT_THROTTLE_SECONDS,
    ):
        self._adapters = dict(adapters)
        self._cache = cache
        self._clock = clock or time.time
        self._sleep = sleep or time.sleep
        self.retries = retries
        self.retry_backoff = retry_backoff
        self.throttle_seconds = throttle_seconds
        self._last_request_at = None
        self._events = []

    def events(self):
        return tuple(self._events)

    def sources(self):
        return tuple(name for name in SOURCE_PRIORITY if name in self._adapters)

    def lookup(self, isin):
        normalized = normalize_isin(isin)
        if normalized is None:
            return FetchResult(isin=isin, failure_code=FAILURE_INVALID_ISIN)
        cached = self._cached_answer(normalized)
        if cached is not None:
            return cached
        if not self._claim_refresh():
            return FetchResult(isin=normalized, failure_code=FAILURE_RATE_LIMITED)
        return self._collect(normalized)

    def refresh(self, isin):
        normalized = normalize_isin(isin)
        if normalized is None:
            return FetchResult(isin=isin, failure_code=FAILURE_INVALID_ISIN)
        return self._collect(normalized)

    def _collect(self, isin):
        values = {}
        sources = {}
        failures = []
        for source in SOURCE_PRIORITY:
            adapter = self._adapters.get(source)
            if adapter is None:
                continue
            result = self._fetch_session(source, isin, adapter)
            if result.has_facts():
                self._record(source, isin, True, result.failure_code)
                _absorb(values, sources, source, result)
                if len(values) == len(INSTRUMENT_FIELDS):
                    break
            else:
                code = _empty_code(result.failure_code)
                failures.append((source, code))
                self._record(source, isin, False, code)
        if len(values) < len(INSTRUMENT_FIELDS):
            seed = snapshot_lookup(isin)
            if seed is not None:
                _absorb(values, sources, SNAPSHOT_SOURCE, seed)
        if not values:
            return self._total_failure(isin, failures)
        return _merged_result(isin, values, sources)

    def _cached_answer(self, isin):
        values = {}
        sources = {}
        failures = []
        seen = False
        for source in SOURCE_PRIORITY:
            cached = self._cache.session_result(source, isin)
            if cached is None:
                continue
            seen = True
            if cached.has_facts():
                _absorb(values, sources, source, cached)
            else:
                failures.append((source, cached.failure_code))
        if not seen:
            return None
        if not values:
            seed = snapshot_lookup(isin)
            if seed is not None:
                _absorb(values, sources, SNAPSHOT_SOURCE, seed)
        if values:
            return _merged_result(isin, values, sources)
        return self._total_failure(isin, failures)

    def _claim_refresh(self):
        try:
            self._cache.begin_refresh()
            return True
        except CooldownActive:
            return False

    def _fetch_session(self, source, isin, adapter):
        cached = self._cache.session_result(source, isin)
        if cached is not None:
            return cached

        def fetcher():
            self._throttle()
            return self._attempt(source, isin, adapter)

        return self._cache.fetch_session(source, isin, fetcher)

    def _attempt(self, source, isin, adapter):
        attempt = 0
        while True:
            result = self._safe_fetch(adapter, isin)
            if result.failure_code not in _RETRYABLE or attempt >= self.retries:
                return result
            attempt += 1
            self._pause(self.retry_backoff * attempt)

    def _safe_fetch(self, adapter, isin):
        try:
            result = adapter.fetch(isin)
        except TimeoutError:
            return FetchResult(isin=isin, failure_code=FAILURE_TIMEOUT)
        except Exception:
            return FetchResult(isin=isin, failure_code=FAILURE_UNREACHABLE)
        if not isinstance(result, FetchResult):
            return FetchResult(isin=isin, failure_code=FAILURE_MALFORMED)
        return result

    def _throttle_wait(self):
        if self.throttle_seconds <= 0 or self._last_request_at is None:
            return 0.0
        return max(0.0, self.throttle_seconds - (self._clock() - self._last_request_at))

    def _throttle(self):
        wait = self._throttle_wait()
        if wait > 0:
            self._sleep(wait)
        self._last_request_at = self._clock()

    def _pause(self, delay):
        wait = max(delay, self._throttle_wait())
        if wait > 0:
            self._sleep(wait)
        self._last_request_at = self._clock()

    def _record(self, source, isin, ok, failure_code):
        self._events.append(
            SourceEvent(
                source=source,
                isin=isin,
                ok=ok,
                failure_code=failure_code,
                at=self._clock(),
            )
        )

    def _total_failure(self, isin, failures):
        codes = [_empty_code(code) for _, code in failures]
        if codes and all(code == FAILURE_UNREACHABLE for code in codes):
            return FetchResult(isin=isin, failure_code=FAILURE_OFFLINE)
        return FetchResult(isin=isin, failure_code=_dominant_failure(codes))


def default_adapters(transport, timeout=DEFAULT_TIMEOUT):
    from . import bse, nsdl, nse, rbi

    modules = {"NSDL": nsdl, "RBI": rbi, "NSE": nse, "BSE": bse}
    adapters = {}
    for source in SOURCE_PRIORITY:
        adapter_class = getattr(modules[source], _ADAPTER_CLASS[source])
        adapters[source] = adapter_class(transport=transport, timeout=timeout)
    return adapters


def build_default_service(cache, transport, **kwargs):
    return BondMasterService(default_adapters(transport), cache, **kwargs)


def _summary(service, cache):
    summary = {}
    view = health_view(service) if service is not None else None
    for source in SOURCE_PRIORITY:
        if view is None:
            status = "idle"
            failure_code = FAILURE_OK
        else:
            entry = view.status(source)
            failure_code = entry.failure_code
            status = _SOURCE_STATUS.get(failure_code, "unknown")
        as_of = None
        if cache is not None:
            try:
                as_of = cache.as_of_for(source)
            except Exception:
                as_of = None
        summary[source] = {
            "status": status,
            "failure_code": failure_code,
            "as_of": as_of,
        }
    return summary


def refresh_all(db_path, trigger="manual", transport=None):
    try:
        cache = shared_cache(db_path)
        if not cache.refresh_allowed():
            return _summary(None, cache)
        if trigger == "auto" and not _claim_auto(db_path):
            return _summary(None, cache)
        cache.begin_refresh()
        service = build_default_service(cache, transport)
        for isin in _known_isins(db_path):
            result = service.refresh(isin)
            if result is not None and result.has_facts():
                cache.save(_bond_record(result))
        return _summary(service, cache)
    except Exception:
        try:
            return _summary(None, shared_cache(db_path))
        except Exception:
            return {}
