from .queries import status_overview
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


def bond_discount_detail(conn, bond_id):
    try:
        row = conn.execute(
            "SELECT id, company, isin, amount, maturity, face_value, watch_investment "
            "FROM bonds WHERE id = ?",
            (bond_id,),
        ).fetchone()
    except Exception as exc:
        raise AppError("ERR-bond-discount", f"bond query failed for {bond_id!r}: {exc}") from exc
    if row is None:
        raise AppError("ERR-bond-discount", f"bond not found: {bond_id!r}")
    discount, source = bond_discount(dict(row))
    if discount is None:
        display = "not recorded"
    else:
        display = f"{discount:.2f}"
    return {
        "bond_id": row["id"],
        "company": row["company"],
        "isin": row["isin"],
        "discount": discount,
        "display": display,
        "source": source,
    }


def discount_report(conn):
    try:
        rows = conn.execute(
            "SELECT id, company, isin, amount, maturity, face_value, watch_investment "
            "FROM bonds ORDER BY id"
        ).fetchall()
    except Exception as exc:
        raise AppError("ERR-bond-discount", f"bond query failed: {exc}") from exc
    entries = []
    total = 0.0
    recorded = 0
    for row in rows:
        discount, source = bond_discount(dict(row))
        entries.append(
            {
                "bond_id": row["id"],
                "company": row["company"],
                "isin": row["isin"],
                "discount": discount,
                "recorded": discount is not None,
                "source": source,
            }
        )
        if discount is not None:
            total += discount
            recorded += 1
    return {
        "rows": entries,
        "totals": {
            "discount": total,
            "recorded": recorded,
            "not_recorded": len(entries) - recorded,
            "bond_count": len(entries),
        },
    }


def tds_deduction(payout_amount, rate=TDS_RATE):
    if isinstance(payout_amount, bool) or not isinstance(payout_amount, (int, float)):
        raise AppError("ERR-tds-compute", f"payout amount must be numeric: {payout_amount!r}")
    value = float(payout_amount)
    if value < 0:
        raise AppError("ERR-tds-compute", f"payout amount must be non-negative: {payout_amount!r}")
    if isinstance(rate, bool) or not isinstance(rate, (int, float)):
        raise AppError("ERR-tds-compute", f"tDS rate must be numeric: {rate!r}")
    rate_value = float(rate)
    if rate_value <= 0 or rate_value > 1:
        raise AppError("ERR-tds-compute", f"tDS rate must be in (0, 1]: {rate!r}")
    tds = value * rate_value
    return {"payout": value, "rate": rate_value, "tds": tds, "net": value - tds}


def tds_report(conn):
    try:
        rows = conn.execute(
            "SELECT id, company, isin, tenure_months, payment_type, interest_payout "
            "FROM bonds ORDER BY id"
        ).fetchall()
    except Exception as exc:
        raise AppError("ERR-tds-compute", f"bond query failed: {exc}") from exc
    entries = []
    annual_gross_total = 0.0
    annual_tds_total = 0.0
    annual_net_total = 0.0
    computable = 0
    for row in rows:
        interest = row["interest_payout"]
        tenure = row["tenure_months"]
        if interest is None or tenure is None:
            entries.append(
                {
                    "bond_id": row["id"],
                    "company": row["company"],
                    "isin": row["isin"],
                    "computable": False,
                }
            )
            continue
        try:
            tenure_value = int(tenure)
        except (TypeError, ValueError) as exc:
            raise AppError(
                "ERR-tds-compute",
                f"bond {row['isin'] or row['company']!r}: unparseable tenure {tenure!r}",
            ) from exc
        if tenure_value < 1:
            raise AppError(
                "ERR-tds-compute",
                f"bond {row['isin'] or row['company']!r}: tenure must be positive: {tenure!r}",
            )
        cycle = payment_cycle_of(row["payment_type"]) or "monthly"
        gross = (float(interest) / tenure_value) * (3 if cycle == "quarterly" else 1)
        deduction = tds_deduction(gross)
        annual_gross = gross * 12
        annual_tds = deduction["tds"] * 12
        annual_net = deduction["net"] * 12
        entries.append(
            {
                "bond_id": row["id"],
                "company": row["company"],
                "isin": row["isin"],
                "computable": True,
                "cycle": cycle,
                "per_month": gross,
                "tds": deduction["tds"],
                "net": deduction["net"],
                "annual_gross": annual_gross,
                "annual_tds": annual_tds,
                "annual_net": annual_net,
            }
        )
        annual_gross_total += annual_gross
        annual_tds_total += annual_tds
        annual_net_total += annual_net
        computable += 1
    return {
        "rows": entries,
        "totals": {
            "annual_gross": annual_gross_total,
            "annual_tds": annual_tds_total,
            "annual_net": annual_net_total,
            "computable": computable,
            "not_computable": len(entries) - computable,
        },
    }


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
                "month": f"{start.year + (start.month - 1 + offset) // 12:04d}-{(start.month - 1 + offset) % 12 + 1:02d}",
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


def pnl_summary(conn, today=None):
    try:
        overview = status_overview(conn, today)
        investment = float(
            conn.execute("SELECT COALESCE(SUM(amount), 0) AS value FROM bonds").fetchone()["value"]
        )
        till_return = float(
            conn.execute(
                "SELECT COALESCE(SUM(amount), 0) AS value FROM payment_ledger "
                "WHERE paid = 1 AND amount > 0"
            ).fetchone()["value"]
        )
    except AppError as exc:
        raise AppError("ERR-dashboard-pnl", f"status computation failed: {exc.message}") from exc
    except Exception as exc:
        raise AppError("ERR-dashboard-pnl", f"pnl query failed: {exc}") from exc
    ongoing_tl = 0.0
    for entry in overview:
        if entry["status"] == "On-going":
            ongoing_tl += float(entry["amount"] or 0)
    return {
        "till_return": till_return,
        "investment": investment,
        "pnl": till_return - investment,
        "ongoing_tl": ongoing_tl,
        "l2_status": PNL_L2_STATUS,
        "l2_note": PNL_L2_NOTE,
    }
