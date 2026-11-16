import pytest
from datetime import date
from src.maturity import months_remaining, months_remaining_from_row
from src.db import init_db
from src.validators import AppError
import tempfile
import os


def test_months_remaining_monthly():
    """Monthly payout: 24 months from Jan 2024 to Jan 2026"""
    result = months_remaining(
        "2024-01-15",
        "2026-01-15",
        "monthly"
    )
    assert result == 24, f"Expected 24, got {result}"


def test_months_remaining_quarterly():
    """Quarterly payout: 8 quarters from Feb 2024 to Feb 2026"""
    result = months_remaining(
        "2024-02-15",
        "2026-02-15",
        "quarterly"
    )
    assert result == 8, f"Expected 8, got {result}"


def test_months_remaining_annual():
    """Annual payout: 2 years from Jan 2024 to Jan 2026"""
    result = months_remaining(
        "2024-01-15",
        "2026-01-15",
        "annual"
    )
    assert result == 2, f"Expected 2, got {result}"


def test_months_remaining_mid_life():
    """Mid-life purchase: Jul 2024 to Jan 2026 = 18 months monthly"""
    result = months_remaining(
        "2024-07-15",
        "2026-01-15",
        "monthly"
    )
    assert result == 18, f"Expected 18, got {result}"


def test_months_remaining_none_when_no_maturity():
    """Returns None when maturity_date is None"""
    result = months_remaining(
        "2024-01-15",
        None,
        "monthly"
    )
    assert result is None, f"Expected None, got {result}"


def test_months_remaining_zero_when_matured():
    """Returns 0 when maturity <= purchase"""
    result = months_remaining(
        "2026-01-15",
        "2026-01-15",
        "monthly"
    )
    assert result == 0, f"Expected 0, got {result}"


def test_months_remaining_from_row():
    """Test convenience function from row dict"""
    row = {
        "maturity_date": "2026-01-15",
        "purchase_date": "2024-01-15",
        "payout_cycle": "monthly",
    }
    result = months_remaining_from_row(row)
    assert result == 24, f"Expected 24, got {result}"


def test_db_migration_maturity_date():
    """Test that init_db adds maturity_date column"""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    try:
        init_db(db_path)
        import sqlite3
        conn = sqlite3.connect(db_path)
        cols = [row[1] for row in conn.execute("PRAGMA table_info(bonds)")]
        assert "maturity_date" in cols, f"maturity_date not in columns: {cols}"
        conn.close()
    finally:
        os.unlink(db_path)


def test_db_migration_listing_status():
    """Test that init_db adds listing_status column with CHECK"""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    try:
        init_db(db_path)
        import sqlite3
        conn = sqlite3.connect(db_path)
        cols = [row[1] for row in conn.execute("PRAGMA table_info(bonds)")]
        assert "listing_status" in cols, f"listing_status not in columns: {cols}"

        # Test CHECK constraint
        conn.execute("INSERT INTO bonds (company, isin, amount, start_date, end_date, tenure_months, credit_day, listing_status) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                     ("Test", "IN1234567890", 1000, "2024-01-01", "2025-01-01", 12, 1, "listed"))
        conn.execute("INSERT INTO bonds (company, isin, amount, start_date, end_date, tenure_months, credit_day, listing_status) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                     ("Test2", "IN1234567891", 1000, "2024-01-01", "2025-01-01", 12, 1, "unlisted"))
        conn.execute("INSERT INTO bonds (company, isin, amount, start_date, end_date, tenure_months, credit_day, listing_status) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                     ("Test3", "IN1234567892", 1000, "2024-01-01", "2025-01-01", 12, 1, "unknown"))

        # This should fail
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute("INSERT INTO bonds (company, isin, amount, start_date, end_date, tenure_months, credit_day, listing_status) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                         ("Test4", "IN1234567893", 1000, "2024-01-01", "2025-01-01", 12, 1, "invalid"))
        conn.close()
    finally:
        os.unlink(db_path)


def test_months_remaining_edge_cases():
    """Additional edge cases"""
    # Jan 31 to Feb 28 monthly = 1 month
    result = months_remaining('2024-01-31', '2024-02-28', 'monthly')
    assert result == 1, f"Expected 1, got {result}"

    # Jan 15 to Mar 15 quarterly = 2 months / 3 = 0 (less than one quarter)
    result = months_remaining('2024-01-15', '2024-03-15', 'quarterly')
    assert result == 0, f"Expected 0, got {result}"

    # Jan 15 to Apr 15 quarterly = 3 months / 3 = 1
    result = months_remaining('2024-01-15', '2024-04-15', 'quarterly')
    assert result == 1, f"Expected 1, got {result}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])