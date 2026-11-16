from datetime import date
from .validators import parse_date_value, AppError

CYCLE_STEPS = {
    "monthly": 1,
    "quarterly": 3,
    "annual": 12,
    "yearly": 12,
}


def months_remaining(purchase_date, maturity_date, payout_cycle):
    """
    Compute the number of pending payout instances from the first payout
    on/after purchase_date through maturity_date, stepping by payout_cycle.

    This computes the month difference between purchase and maturity,
    then divides by the cycle step (monthly=1, quarterly=3, annual=12).

    Args:
        purchase_date: date or ISO string (YYYY-MM-DD)
        maturity_date: date or ISO string (YYYY-MM-DD) or None
        payout_cycle: str - 'monthly', 'quarterly', 'annual', or 'yearly'

    Returns:
        int or None: number of payout instances remaining, or None if maturity_date is None
    """
    if maturity_date is None:
        return None

    try:
        purchase = parse_date_value(purchase_date, "purchase_date")
        maturity = parse_date_value(maturity_date, "maturity_date")
    except AppError:
        return None

    if maturity <= purchase:
        return 0

    step = CYCLE_STEPS.get(payout_cycle, 1)

    # Compute month difference: (maturity_year - purchase_year) * 12 + (maturity_month - purchase_month)
    month_diff = (maturity.year - purchase.year) * 12 + (maturity.month - purchase.month)

    # Number of payout instances = month_diff / step (integer division)
    # This counts payouts from the first on/after purchase through maturity
    return month_diff // step


def months_remaining_from_row(row, today=None):
    """
    Compute months_remaining from a bond row dict or sqlite3.Row.

    Args:
        row: dict or sqlite3.Row with keys maturity_date, purchase_date, payout_cycle
        today: optional date for reference (unused, kept for compatibility)

    Returns:
        int or None
    """
    # Handle both dict and sqlite3.Row (which doesn't have .get())
    if hasattr(row, "get"):
        maturity_date = row.get("maturity_date")
        purchase_date = row.get("purchase_date")
        payout_cycle = row.get("payout_cycle", "monthly")
    else:
        # sqlite3.Row - use dictionary-style access
        keys = row.keys()
        maturity_date = row["maturity_date"] if "maturity_date" in keys else None
        purchase_date = row["purchase_date"] if "purchase_date" in keys else None
        payout_cycle = row["payout_cycle"] if "payout_cycle" in keys else "monthly"

    if not maturity_date or not purchase_date:
        return None

    return months_remaining(purchase_date, maturity_date, payout_cycle)