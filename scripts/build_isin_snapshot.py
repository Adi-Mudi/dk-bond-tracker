#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import io
import json
import sys
import urllib.request
from datetime import datetime
from pathlib import Path

REPO = "captn3m0/india-isin-data"
LICENSE = "CC0-1.0"
SOURCE_LABEL = "india-isin-data (CC0)"
DATASET_URL = f"https://github.com/{REPO}"

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "src" / "bond_master" / "data" / "india_isin_snapshot.json"

DATE_PATTERNS = ("%d-%b-%Y", "%d-%b-%y", "%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y")


def _clean(value):
    return "" if value is None else str(value).strip()


def _coupon(value):
    text = _clean(value).replace(",", "").replace("%", "")
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def _maturity(value):
    text = _clean(value)
    if not text:
        return None
    for pattern in DATE_PATTERNS:
        try:
            return datetime.strptime(text, pattern).date().isoformat()
        except ValueError:
            continue
    return None


def _release_version():
    request = urllib.request.Request(
        f"https://api.github.com/repos/{REPO}/releases/latest",
        headers={"Accept": "application/vnd.github+json", "User-Agent": "dk-bond-tracker-snapshot"},
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        payload = json.loads(response.read().decode("utf-8"))
    return payload["tag_name"].lstrip("v"), payload["assets"]


def _download(url):
    request = urllib.request.Request(
        url, headers={"User-Agent": "dk-bond-tracker-snapshot"}
    )
    with urllib.request.urlopen(request, timeout=120) as response:
        return response.read().decode("utf-8")


def transform(text):
    rows = {}
    reader = csv.DictReader(io.StringIO(text.lstrip("\ufeff")))
    for record in reader:
        isin = _clean(record.get("ISIN")).upper()
        if not isin:
            continue
        cfi = _clean(record.get("CFI")).upper()
        if not cfi.startswith("D"):
            continue
        fields = {}
        company = _clean(record.get("NAME_OF_ISSUER"))
        if company:
            fields["company"] = company
        coupon = _coupon(record.get("INTEREST_RATE"))
        if coupon is not None:
            fields["coupon"] = coupon
        maturity = _maturity(record.get("MATURITY_DATE"))
        if maturity is not None:
            fields["maturity"] = maturity
        if not fields:
            continue
        rows[isin] = fields
    return rows


def build(csv_text, version, asset_name):
    rows = transform(csv_text)
    return {
        "name": "india-isin-data",
        "version": version,
        "source": SOURCE_LABEL,
        "license": LICENSE,
        "url": DATASET_URL,
        "dataset": f"{DATASET_URL}/releases",
        "generated_from": asset_name,
        "field_model": "AF-01 instrument facts present in the dataset",
        "columns_used": {
            "ISIN": "isin",
            "NAME_OF_ISSUER": "company",
            "INTEREST_RATE": "coupon",
            "MATURITY_DATE": "maturity",
        },
        "rows": rows,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(prog="build-isin-snapshot")
    parser.add_argument("--csv", help="use a local CSV file instead of downloading")
    parser.add_argument("--output", default=str(OUTPUT))
    args = parser.parse_args(argv)

    if args.csv:
        csv_text = Path(args.csv).read_text(encoding="utf-8")
        version, asset_name = "local", Path(args.csv).name
    else:
        version, assets = _release_version()
        asset = next(
            (item for item in assets if item["name"].lower().endswith(".csv")), None
        )
        if asset is None:
            print("no CSV asset on the latest release", file=sys.stderr)
            return 1
        asset_name = asset["name"]
        csv_text = _download(asset["browser_download_url"])

    document = build(csv_text, version, asset_name)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(document, ensure_ascii=False, separators=(",", ":"), sort_keys=True),
        encoding="utf-8",
    )
    print(f"wrote {len(document['rows'])} rows to {output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
