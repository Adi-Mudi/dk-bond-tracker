from pathlib import Path

import pytest

from src.db import get_conn
from src.import_xlsm import (
    BOND_SHEET_TITLE,
    extract_bond_master,
    extract_payment_grid,
    import_workbook,
    locate_sheet,
    open_workbook,
    recompute_kl,
    reconcile,
)

WORKBOOK = Path(
    "/mnt/Just_Do_It/02_Devp_Soft/01_Adi-Mudi/04_Bonds/01_excel_dashboard/v5.5_40L_Project_Tracker.xlsm"
)

EXPECTED_ISINS = [
    "INE420C07130",
    "INE101Q07BS1",
    "INE342T07569",
    "INE0BUS07CE3",
    "INE07HK07866",
    "INE08XP07431",
    "INE109C07139",
    "INE926R07019",
    "INE04UP07162",
    "INE0NES07329",
    "INE572J07810",
    "INE104W07245",
    "INE01XO07066",
    "INE04Q907199",
    "INE0I5X07042",
]

WORKBOOK_INVESTMENT = 1037142.01
WORKBOOK_TILL_RETURN = 56227.88
WORKBOOK_BALANCE = -1165738.34
PRD_TILL_RETURN = 111638.57
PRD_BALANCE = -925503.44


@pytest.fixture(scope="module")
def imported(tmp_path_factory):
    db_path = tmp_path_factory.mktemp("tc24") / "import_real.db"
    summary = import_workbook(WORKBOOK, db_path)
    return summary, db_path


@pytest.fixture(scope="module")
def extracted():
    workbook = open_workbook(WORKBOOK)
    try:
        values_name = locate_sheet(workbook.values, BOND_SHEET_TITLE)
        formulas_name = locate_sheet(workbook.formulas, BOND_SHEET_TITLE)
        bonds = extract_bond_master(
            workbook.values[values_name], workbook.formulas[formulas_name]
        )
        months, cells = extract_payment_grid(workbook.values[values_name])
    finally:
        workbook.values.close()
        workbook.formulas.close()
    return bonds, months, cells


def test_real_workbook_present():
    assert WORKBOOK.is_file()


def test_import_summary_counts(imported):
    summary, _ = imported
    assert summary["bonds"] == 15
    assert summary["months"] == 83
    assert summary["ledger_rows"] > 0


def test_month_headers_runtime_derived(extracted):
    _, months, _ = extracted
    assert len(months) == 83
    assert months[0] == "2025-09"
    assert months[-1] == "2032-07"


def test_isins_match_feasibility_list(extracted):
    bonds, _, _ = extracted
    assert len(bonds) == 15
    assert [bond["isin"] for bond in bonds] == EXPECTED_ISINS


def test_ledger_rows_equal_positive_cells(imported, extracted):
    summary, db_path = imported
    _, _, cells = extracted
    positive = sum(
        1 for row in cells for value in row.values() if value is not None and value > 0
    )
    assert positive == 84
    assert summary["ledger_rows"] == positive
    with get_conn(db_path) as conn:
        bond_rows = conn.execute("SELECT COUNT(*) FROM bonds").fetchone()[0]
        ledger_rows = conn.execute("SELECT COUNT(*) FROM payment_ledger").fetchone()[0]
        unpaid_rows = conn.execute(
            "SELECT COUNT(*) FROM payment_ledger WHERE amount IS NULL OR amount <= 0"
        ).fetchone()[0]
    assert bond_rows == 15
    assert ledger_rows == positive
    assert unpaid_rows == 0


def test_k_and_l_recompute_totals(extracted):
    bonds, _, cells = extracted
    k_total = 0.0
    l_total = 0.0
    for bond, row_cells in zip(bonds, cells):
        k_value, l_value = recompute_kl(row_cells, bond["maturity"])
        k_total += k_value
        l_total += l_value
    assert k_total == pytest.approx(WORKBOOK_TILL_RETURN, abs=0.01)
    assert l_total == pytest.approx(WORKBOOK_BALANCE, abs=0.01)


def test_reconcile_l1_pending_and_workbook_actuals(imported):
    summary, _ = imported
    report = summary["reconcile"]
    assert report["l1_status"] == "PENDING_BASELINE"
    computed = report["computed"]
    assert computed["bond_count"] == 15
    assert computed["investment"] == pytest.approx(WORKBOOK_INVESTMENT, abs=0.01)
    assert computed["till_return"] == pytest.approx(WORKBOOK_TILL_RETURN, abs=0.01)
    assert computed["balance"] == pytest.approx(WORKBOOK_BALANCE, abs=0.01)
    assert report["match_flags"]["investment_vs_workbook"] is True
    assert report["match_flags"]["till_return_vs_workbook"] is True
    assert report["match_flags"]["balance_vs_workbook"] is True


def test_reconcile_carries_prd_baseline_with_match_false(imported):
    summary, _ = imported
    report = summary["reconcile"]
    prd = report["baselines"]["prd"]
    assert prd["investment"] == WORKBOOK_INVESTMENT
    assert prd["till_return"] == PRD_TILL_RETURN
    assert prd["balance"] == PRD_BALANCE
    assert report["baselines"]["workbook"]["till_return"] == WORKBOOK_TILL_RETURN
    assert report["baselines"]["workbook"]["balance"] == WORKBOOK_BALANCE
    assert report["match_flags"]["investment_vs_prd"] is True
    assert report["match_flags"]["till_return_vs_prd"] is False
    assert report["match_flags"]["balance_vs_prd"] is False
    assert report["mismatch_deltas"]["till_return_vs_prd"] == pytest.approx(
        WORKBOOK_TILL_RETURN - PRD_TILL_RETURN, abs=0.01
    )
    assert report["mismatch_deltas"]["balance_vs_prd"] == pytest.approx(
        WORKBOOK_BALANCE - PRD_BALANCE, abs=0.01
    )
    assert report["computed"]["till_return"] == pytest.approx(WORKBOOK_TILL_RETURN, abs=0.01)
    assert report["computed"]["balance"] == pytest.approx(WORKBOOK_BALANCE, abs=0.01)


def test_reconcile_never_alters_computed_figures():
    bonds = [
        {"row": 2, "investment": 100.0, "maturity": 50.0},
        {"row": 3, "investment": 200.0, "maturity": 60.0},
    ]
    baseline = {
        "prd": {"investment": 300.0, "till_return": 999.0, "balance": -888.0},
        "workbook": {"investment": 300.0, "till_return": 30.0, "balance": -80.0},
    }
    report = reconcile(bonds, [10.0, 20.0], baseline)
    assert report["computed"]["investment"] == 300.0
    assert report["computed"]["till_return"] == 30.0
    assert report["computed"]["balance"] == -80.0
    assert report["match_flags"]["investment_vs_prd"] is True
    assert report["match_flags"]["till_return_vs_prd"] is False
    assert report["match_flags"]["balance_vs_prd"] is False
    assert report["match_flags"]["till_return_vs_workbook"] is True
    assert report["match_flags"]["balance_vs_workbook"] is True
