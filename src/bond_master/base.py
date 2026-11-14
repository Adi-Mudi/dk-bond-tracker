from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping, Protocol

INSTRUMENT_FIELDS = (
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
)

POSITION_FIELDS = (
    "amount",
    "quantity",
    "start_date",
    "end_date",
    "credit_day",
)

RESULT_FIELDS = ("isin",) + INSTRUMENT_FIELDS

LISTING_STATUSES = ("listed", "unlisted", "unknown")

SOURCE_PRIORITY = ("NSDL", "RBI", "NSE", "BSE")

FAILURE_OK = "OK"
FAILURE_NOT_FOUND = "NOT_FOUND"
FAILURE_UNREACHABLE = "UNREACHABLE"
FAILURE_TIMEOUT = "TIMEOUT"
FAILURE_BLOCKED = "BLOCKED"
FAILURE_MALFORMED = "MALFORMED"
FAILURE_PARSE_ERROR = "PARSE_ERROR"
FAILURE_RATE_LIMITED = "RATE_LIMITED"
FAILURE_OFFLINE = "OFFLINE"
FAILURE_INVALID_ISIN = "INVALID_ISIN"

FAILURE_CODES = (
    FAILURE_OK,
    FAILURE_NOT_FOUND,
    FAILURE_UNREACHABLE,
    FAILURE_TIMEOUT,
    FAILURE_BLOCKED,
    FAILURE_MALFORMED,
    FAILURE_PARSE_ERROR,
    FAILURE_RATE_LIMITED,
    FAILURE_OFFLINE,
    FAILURE_INVALID_ISIN,
)


@dataclass(frozen=True)
class FetchResult:
    isin: str | None = None
    company: str | None = None
    coupon: float | None = None
    payout_cycle: str | None = None
    face_value: float | None = None
    rating: str | None = None
    rating_agency: str | None = None
    issuer_type: str | None = None
    secured: int | None = None
    listing_status: str | None = None
    maturity: str | None = None
    sources: Mapping[str, str] = field(default_factory=dict)
    failure_code: str = FAILURE_OK

    def facts(self) -> dict[str, object]:
        return {name: getattr(self, name) for name in INSTRUMENT_FIELDS}

    def source_of(self, name: str) -> str | None:
        return self.sources.get(name)

    def has_facts(self) -> bool:
        return any(getattr(self, name) is not None for name in INSTRUMENT_FIELDS)


class Adapter(Protocol):
    name: str

    def fetch(self, isin: str) -> FetchResult:
        ...
