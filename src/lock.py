from datetime import date

from .engine import derive_health
from .status import tenure_month_map
from .validators import AppError


def _normalize_company(value):
    return " ".join(str(value or "").split()).lower()


def _normalize_isin(value):
    return str(value or "").strip().upper()


def check_add_allowed(company_normalized, isin, conn):
    company_key = _normalize_company(company_normalized)
    isin_key = _normalize_isin(isin)
    rows = conn.execute(
        "SELECT id, company, isin, start_date, end_date, tenure_months, credit_day "
        "FROM bonds WHERE watch_state = 'holding' ORDER BY id"
    ).fetchall()
    for row in rows:
        name_match = bool(company_key) and _normalize_company(row["company"]) == company_key
        isin_match = bool(isin_key) and _normalize_isin(row["isin"]) == isin_key
        if not (name_match or isin_match):
            continue
        months = tenure_month_map(conn, row["id"], row["start_date"], row["tenure_months"])
        health = derive_health(row, months, date.today())
        if health in ("On-going", "Danger"):
            raise AppError(
                "ERR-active-position",
                f"Cannot add position: {row['company']} has an active position ({health})",
            )
    return True
