from decimal import Decimal
from pathlib import Path

from banking.accounts import Account, AccountType, AccountRepository
from banking.csv_parser import parse_csv
from banking.models import Transaction, TransactionType
from banking.service import (
    create_account,
    get_credit_card_monthly,
    get_overall_stats,
    get_transactions,
    init_workflow,
    list_accounts,
)
from banking.workflow import FinanceTrackerWorkflow


SAMPLE = """Posting Date,Transaction Date,Amount,Credit Debit Indicator,type,Type Group,Reference,Instructed Currency,Currency Exchange Rate,Instructed Amount,Description,Category,Check Serial Number,Card Ending,Rewards Total,Rewards Type
08/25/2026,08/24/2026,26.81,Debit,POS,POS,,,,,Jetsplash,Automotive Expenses,,,,
08/24/2026,08/24/2026,1182.75,Credit,ACH Credit,ACH Credit,,,,,Payroll Deposit,Paychecks/Salary,,,,
"""


def test_default_accounts(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("FINANCE_APP_DATA_DIR", str(tmp_path))
    init_workflow(tmp_path / "bank")
    accounts = list_accounts()
    names = {a["name"] for a in accounts}
    assert "Checking" in names
    assert any(a["account_type"] == "credit_card" for a in accounts)


def test_import_stamps_account(tmp_path: Path):
    bank_dir = tmp_path / "bank"
    csv_path = tmp_path / "stmt.csv"
    csv_path.write_text(SAMPLE, encoding="utf-8")
    workflow = FinanceTrackerWorkflow(data_dir=bank_dir)
    txns, stats = workflow.process_csv_file(csv_path, account="Credit Card 1")
    assert stats["account"] == "Credit Card 1"
    assert all(t.account == "Credit Card 1" for t in txns)
    assert any(t.is_expense for t in txns)
    assert any(t.is_income for t in txns)


def test_stats_filter_by_account(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("FINANCE_APP_DATA_DIR", str(tmp_path))
    bank_dir = tmp_path / "bank"
    init_workflow(bank_dir)
    create_account("Amex", "credit_card")
    create_account("Checking", "checking")

    workflow = FinanceTrackerWorkflow(data_dir=bank_dir)
    csv_path = tmp_path / "a.csv"
    csv_path.write_text(SAMPLE, encoding="utf-8")
    workflow.process_csv_file(csv_path, account="Amex")

    # second file only checking income-like
    other = tmp_path / "b.csv"
    other.write_text(
        "Date,Description,Amount,Balance\n2026-08-01,Salary,2000.00,2000.00\n",
        encoding="utf-8",
    )
    workflow.process_csv_file(other, account="Checking")

    amex_stats = get_overall_stats(account="Amex")
    checking_stats = get_overall_stats(account="Checking")
    assert Decimal(amex_stats["total_expenses"]) == Decimal("26.81")
    assert Decimal(checking_stats["total_income"]) == Decimal("2000.00")

    amex_txns = get_transactions(account="Amex", per_page=100)
    assert all(t.get("account") == "Amex" for t in amex_txns)

    cards = get_credit_card_monthly()
    amex_card = next(c for c in cards["cards"] if c["account"]["name"] == "Amex")
    assert Decimal(amex_card["total_expenses"]) == Decimal("26.81")
    assert amex_card["months"]
