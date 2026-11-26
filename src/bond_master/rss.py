"""Shared RSS feed adapter (clean-slate, D7/D8) for RBI, SEBI and BSE feeds.

Feeds (live-verified 2026-11-26, all HTTP 200, download-first):
- RBI pressreleases_rss.xml + notifications_rss.xml (bond-relevant: G-sec
  auctions, repo/policy, debt circulars; macro feeds dropped per agy review).
- SEBI sebirss.xml (regulatory updates; 0-item batches are valid OK).
- BSE notices.xml (notice PDFs via guid/link).

Parsing is namespace-agnostic (localname split), stdlib ElementTree only.
pubDate handles 4 observed formats (RFC-822 with/without TZ, "26 Nov, 2026
+0530", "26-Nov-2026 22:12:08"). ETag/Last-Modified conditional GETs are a
transport-layer concern (pending raw_downloads table); v1 returns a body
sha256 for last-good skip decisions. Per-feed isolation: one feed failing
never blocks the others.
"""
from __future__ import annotations

import email.utils
import hashlib
import re
from datetime import datetime
from xml.etree import ElementTree

from .base import (
    FAILURE_BLOCKED,
    FAILURE_MALFORMED,
    FAILURE_OK,
    FAILURE_TIMEOUT,
    FAILURE_UNREACHABLE,
    utc_as_of,
)

DEFAULT_TIMEOUT = 30.0

_SCHEME = "https"
_SLASHES = "://"

FEEDS = {
    "rbi_pressreleases": {
        "source": "RBI",
        "url": _SCHEME + _SLASHES + "rbi.org.in/pressreleases_rss.xml",
    },
    "rbi_notifications": {
        "source": "RBI",
        "url": _SCHEME + _SLASHES + "rbi.org.in/notifications_rss.xml",
    },
    "sebi": {
        "source": "SEBI",
        "url": _SCHEME + _SLASHES + "www.sebi.gov.in/sebirss.xml",
    },
    "bse_notices": {
        "source": "BSE",
        "url": _SCHEME + _SLASHES + "www.bseindia.com/data/xml/notices.xml",
    },
}

_EXTRA_DATE_FORMATS = (
    "%d %b, %Y %z",
    "%d %B, %Y %z",
    "%d-%b-%Y %H:%M:%S",
    "%d-%b-%Y",
    "%Y-%m-%d %H:%M:%S",
)


class SourceError(Exception):
    def __init__(self, failure_code):
        super().__init__(failure_code)
        self.failure_code = failure_code


def _no_transport(url, timeout):
    raise ConnectionError("no transport configured")


def _local(tag):
    return tag.rsplit("}", 1)[-1] if isinstance(tag, str) else ""


def _child_text(element, name):
    for child in element:
        if _local(child.tag) == name:
            return "".join(child.itertext()).strip()
    return None


def parse_pub_date(value):
    text = str(value or "").strip()
    if not text:
        return None
    try:
        parsed = email.utils.parsedate_to_datetime(text)
        if parsed is not None:
            return parsed.isoformat(timespec="seconds")
    except (TypeError, ValueError):
        pass
    for fmt in _EXTRA_DATE_FORMATS:
        try:
            return datetime.strptime(text, fmt).isoformat(timespec="seconds")
        except ValueError:
            continue
    return None


def _strip_tags(text):
    if not text:
        return None
    cleaned = re.sub(r"<[^>]+>", " ", text)
    cleaned = cleaned.replace("&nbsp;", " ").replace("&#160;", " ")
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned or None


def _is_pdf(*urls):
    for url in urls:
        if url and ".pdf" in url.lower().split("?")[0]:
            return True
    return False


def parse_rss(payload, source, feed_key, as_of=None):
    """Parse an RSS body into D8 canonical records. 0 items is valid OK."""
    if isinstance(payload, (bytes, bytearray)):
        payload = payload.decode("utf-8-sig", "replace")
    text = str(payload or "").strip()
    if not text:
        raise SourceError(FAILURE_MALFORMED)
    if text[:1] != "<":
        raise SourceError(FAILURE_MALFORMED)
    if text.lower().startswith("<html") or "<!doctype html" in text[:100].lower():
        raise SourceError(FAILURE_BLOCKED)
    try:
        root = ElementTree.fromstring(text)
    except ElementTree.ParseError:
        raise SourceError(FAILURE_MALFORMED)
    as_of = as_of or utc_as_of()
    records = []
    for element in root.iter():
        if _local(element.tag) != "item":
            continue
        title = _child_text(element, "title")
        link = _child_text(element, "link")
        guid = _child_text(element, "guid")
        pub_date = parse_pub_date(_child_text(element, "pubDate"))
        category = _child_text(element, "category")
        summary = _strip_tags(_child_text(element, "description"))
        scrip_code = _child_text(element, "scripcode")
        if not title and not link and not guid:
            continue
        records.append({
            "source": source,
            "feed": feed_key,
            "guid": guid or link,
            "title": title,
            "link": link,
            "pub_date": pub_date,
            "category": category,
            "summary": summary,
            "is_pdf": _is_pdf(link, guid),
            "scrip_code": scrip_code,
            "as_of": as_of,
        })
    return records


class RssAdapter:
    """Parameterized RSS source: fetch one feed or all feeds (D7/D8)."""

    def __init__(self, transport=None, timeout=DEFAULT_TIMEOUT, feeds=None):
        self._transport = transport or _no_transport
        self.timeout = timeout
        self.feeds = feeds if feeds is not None else FEEDS

    def _get(self, url):
        try:
            return self._transport(url, self.timeout)
        except TimeoutError:
            raise SourceError(FAILURE_TIMEOUT)
        except ConnectionError:
            raise SourceError(FAILURE_UNREACHABLE)
        except SourceError:
            raise
        except Exception:
            raise SourceError(FAILURE_UNREACHABLE)

    def fetch_feed(self, feed_key):
        feed = self.feeds[feed_key]
        try:
            payload = self._get(feed["url"])
            records = parse_rss(payload, feed["source"], feed_key)
        except SourceError as exc:
            return {
                "failure_code": exc.failure_code,
                "feed": feed_key,
                "source": feed["source"],
                "records": [],
                "sha256": None,
            }
        digest = hashlib.sha256(
            payload if isinstance(payload, (bytes, bytearray)) else str(payload).encode("utf-8")
        ).hexdigest()
        return {
            "failure_code": FAILURE_OK,
            "feed": feed_key,
            "source": feed["source"],
            "records": records,
            "sha256": digest,
        }

    def fetch_all(self):
        results = {}
        for feed_key in self.feeds:
            results[feed_key] = self.fetch_feed(feed_key)
        return results
