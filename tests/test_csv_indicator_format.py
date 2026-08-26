from decimal import Decimal
from pathlib import Path

from banking.csv_parser import CSVFormat, CSVParser, parse_csv
from banking.models import TransactionType

SAMPLE = """Posting Date,Transaction Date,Amount,Credit Debit Indicator,type,Type Group,Reference,Instructed Currency,Currency Exchange Rate,Instructed Amount,Description,Category,Check Serial Number,Card Ending,Rewards Total,Rewards Type
08/25/2026,08/24/2026,26.81,Debit,POS,POS,,,,,Jetsplash,Automotive Expenses,,,,
08/24/2026,08/24/2026,1182.75,Credit,ACH Credit,ACH Credit,,,,,Deposit Real Radiology L Payroll,Paychecks/Salary,5140050,,,
08/17/2026,08/16/2026,400.00,Debit,POS,POS,,,,,Transfer to Venmo,Transfers,,,,
08/17/2026,08/17/2026,2575.00,Credit,ACH Credit,ACH Credit,,,,,Transfer from Venmo,Transfers,9100001,,,
07/31/2026,07/31/2026,0.01,Credit,Credit,Credit,,,,,Dividend,Investment Income,,,,
"""


def test_detects_indicator_format(tmp_path: Path):
    path = tmp_path / "txns.csv"
    path.write_text(SAMPLE, encoding="utf-8")
    assert CSVParser().detect_format(path) == CSVFormat.INDICATOR


def test_indicator_format_classifies_debit_and_credit(tmp_path: Path):
    path = tmp_path / "txns.csv"
    path.write_text(SAMPLE, encoding="utf-8")
    txns = parse_csv(path)

    assert len(txns) == 5

    jetsplash = next(t for t in txns if "Jetsplash" in t.description)
    assert jetsplash.transaction_type == TransactionType.DEBIT
    assert jetsplash.amount == Decimal("-26.81")
    assert jetsplash.is_expense
    assert not jetsplash.is_income
    assert jetsplash.category and jetsplash.category.name == "Automotive Expenses"

    payroll = next(t for t in txns if "Payroll" in t.description)
    assert payroll.transaction_type == TransactionType.CREDIT
    assert payroll.amount == Decimal("1182.75")
    assert payroll.is_income

    venmo_out = next(t for t in txns if "Transfer to Venmo" in t.description)
    assert venmo_out.is_expense
    assert venmo_out.amount == Decimal("-400.00")

    venmo_in = next(t for t in txns if "Transfer from Venmo" in t.description)
    assert venmo_in.is_income
    assert venmo_in.amount == Decimal("2575.00")


def test_real_upload_fixture_if_present():
    upload = Path("/home/ubuntu/.cursor/projects/workspace/uploads/transactions_504e.csv")
    if not upload.exists():
        return
    txns = parse_csv(upload)
    assert len(txns) > 100
    expenses = [t for t in txns if t.is_expense]
    income = [t for t in txns if t.is_income]
    assert len(expenses) > len(income)
    assert all(t.amount < 0 for t in expenses)
    assert all(t.amount > 0 for t in income)
