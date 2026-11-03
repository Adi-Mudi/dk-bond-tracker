from .queries import status_overview
from .status import month_key
from .validators import AppError, add_months, parse_date_value

TDS_RATE = 0.10
CYCLE_STEPS = {"monthly": 1, "quarterly": 3, "yearly": 12}
PNL_L2_STATUS = "PENDING_CONFIRMATION"
PNL_L2_NOTE = (
    "P&L formula is PROPOSED (L2, owner confirmation required): shown as "
    "Till Return - Investment; the alternative candidate is maturity - investment. "
    "Build proceeds; acceptance does not."
)


def payment_cycle_of(payment_type):
    text = str(payment_type or "").strip().lower()
    if not text:
        return None
    if "quart" in text:
        return "quarterly"
    if "year" in text or "annual" in text:
        return "yearly"
    if "month" in text:
        return "monthly"
    return None


def bond_discount(record):
    face = record.get("face_value")
    invested = record.get("watch_investment")
    if invested is None:
        invested = record.get("amount")
    if face is not None and invested is not None:
        return float(face) - float(invested), "watch-lgh"
    maturity = record.get("maturity")
    amount = record.get("amount")
    if maturity is not None and amount is not None:
        return float(maturity) - float(amount), "maturity-minus-amount"
    return None, "not-recorded"


def payout_schedule(conn, bond_id, cycle):
    cycle_key = str(cycle or "").strip().lower()
    if cycle_key not in CYCLE_STEPS:
        raise AppError(
            "ERR-due-dates",
            f"unknown payment cycle: {cycle!r} (expected monthly, quarterly or yearly)",
        )
    try:
        row = conn.execute(
            "SELECT id, company, isin, start_date, tenure_months, interest_payout, payment_type "
            "FROM bonds WHERE id = ?",
            (bond_id,),
        ).fetchone()
    except Exception as exc:
        raise AppError("ERR-due-dates", f"bond query failed for {bond_id!r}: {exc}") from exc
    if row is None:
        raise AppError("ERR-due-dates", f"bond not found: {bond_id!r}")
    try:
        start = parse_date_value(row["start_date"], "start_date")
    except AppError as exc:
        raise AppError(
            "ERR-due-dates", f"bond {bond_id}: unparseable start month {row['start_date']!r}"
        ) from exc
    try:
        tenure = int(row["tenure_months"])
    except (TypeError, ValueError) as exc:
        raise AppError(
            "ERR-due-dates", f"bond {bond_id}: unparseable tenure {row['tenure_months']!r}"
        ) from exc
    if tenure < 1:
        raise AppError("ERR-due-dates", f"bond {bond_id}: tenure must be positive: {row['tenure_months']!r}")
    step = CYCLE_STEPS[cycle_key]
    interest = row["interest_payout"]
    monthly_amount = None
    if interest is not None:
        monthly_amount = float(interest) / tenure
    instances = []
    offset = 0
    while offset < tenure:
        covered = min(step, tenure - offset)
        amount = None if monthly_amount is None else monthly_amount * covered
        instances.append(
            {
                "month": month_key(add_months(start, offset)),
                "offset": offset,
                "months_covered": covered,
                "partial": covered < step,
                "cycle_amount": None if monthly_amount is None else monthly_amount * step,
                "amount": amount,
                "tds": None if amount is None else amount * TDS_RATE,
                "net": None if amount is None else amount - amount * TDS_RATE,
            }
        )
        offset += step
    total_amount = None
    total_tds = None
    total_net = None
    if monthly_amount is not None:
        total_amount = monthly_amount * tenure
        total_tds = total_amount * TDS_RATE
        total_net = total_amount - total_tds
    return {
        "bond_id": row["id"],
        "company": row["company"],
        "isin": row["isin"],
        "cycle": cycle_key,
        "step_months": step,
        "start_month": f"{start.year:04d}-{start.month:02d}",
        "tenure_months": tenure,
        "monthly_amount": monthly_amount,
        "stored_payment_type": row["payment_type"],
        "instances": instances,
        "instance_count": len(instances),
        "total_amount": total_amount,
        "total_tds": total_tds,
        "total_net": total_net,
    }
