from datetime import date


def _resolve_today(today):
    if today is None:
        try:
            return date.today()
        except Exception:
            return None
    return today


def _default_today():
    return date.today()


from .summary import (
    bond_month_totals,
    portfolio_totals,
    status_overview,
    summary_counts,
    summary_amounts,
    _month_keys_span,
)
from .history import (
    this_month_returns,
    returns_history,
    monthly_history,
    chart_data,
    HISTORY_MONTH_CAP,
)
from .grid import (
    month_label,
    grid_month_columns,
    grid_model,
    free_up_report,
)
from .detail import (
    MONTH_PATTERN,
    received_by_bond,
    portfolio_snapshot,
    position_detail,
    delete_candidate,
)
