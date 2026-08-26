"""
Web application using Eel for finance tracker.

This module provides a desktop web application interface using the Eel framework.
The app runs in a desktop window (Microsoft Edge on macOS) and provides a modern
web-based UI for all finance tracker operations.

Features:
    - Dashboard with statistics and charts
    - Transaction list with search and filters
    - Category breakdown and analysis
    - CSV file import with drag-and-drop
    - Interactive charts using Chart.js
    - Real-time data updates

The module exposes Python functions to JavaScript via Eel's @eel.expose decorator,
allowing the frontend to interact with the backend seamlessly.

Architecture:
    - Frontend: HTML/CSS/JavaScript in web/ directory
    - Backend: Python functions exposed via Eel
    - Communication: Bidirectional via Eel's RPC system

Example:
    >>> from banking.web_app import start_web_app
    >>> 
    >>> # Start web app (opens in browser window)
    >>> start_web_app(port=8080, size=(1200, 800))
    
Or from command line:
    $ finance-tracker-web
"""

import logging
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Optional


from banking.accounts import Account, AccountType
from banking.budget_tracker import BudgetRepository, BudgetTracker
from banking.category_rules_manager import CategoryRulesManager
from banking.config import get_config
from banking.logging_config import setup_logging
from banking.models import Budget, BudgetTemplate, Category, SplitTransaction, Transaction
from banking.recurring_detector import RecurringTransactionDetector
from banking.search_filter import TransactionSearchFilter
from banking.transaction_editor import TransactionEditor
from banking.workflow import FinanceTrackerWorkflow
from banking.analyzer import SpendingAnalyzer

logger = logging.getLogger(__name__)

# Global workflow instance
workflow: Optional[FinanceTrackerWorkflow] = None


def init_workflow(data_dir: Optional[Path] = None) -> None:
    """Initialize the workflow instance."""
    global workflow
    if data_dir is None:
        try:
            from app.paths import get_bank_dir

            data_dir = get_bank_dir()
        except Exception:
            cfg = get_config()
            data_dir = Path(cfg.get("data.directory", Path.home() / ".finance-app" / "bank"))
    workflow = FinanceTrackerWorkflow(data_dir=data_dir)
    logger.info(f"Initialized workflow with data directory: {data_dir}")


def select_file() -> Optional[str]:
    """
    Open file dialog to select CSV file.

    Returns:
        Selected file path or None
    """
    try:
        import tkinter as tk
        from tkinter import filedialog
        
        root = tk.Tk()
        root.withdraw()  # Hide the main window
        
        file_path = filedialog.askopenfilename(
            title="Select CSV File",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")]
        )
        
        root.destroy()
        return file_path if file_path else None
    except Exception as e:
        logger.error(f"Error selecting file: {e}", exc_info=True)
        return None


def import_csv_file(
    file_path: str,
    account: Optional[str] = None,
    auto_categorize: bool = True,
    overwrite: bool = False,
    check_duplicates: bool = True,
    skip_duplicates: bool = True,
) -> Dict:
    """
    Import a CSV file.

    Args:
        file_path: Path to CSV file
        account: Optional account identifier
        auto_categorize: Whether to auto-categorize
        overwrite: Whether to overwrite existing categories
        check_duplicates: Whether to check for duplicates
        skip_duplicates: Whether to skip duplicates

    Returns:
        Dictionary with import statistics
    """
    if workflow is None:
        init_workflow()

    try:
        csv_path = Path(file_path)
        if not csv_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        transactions, stats = workflow.process_csv_file(
            csv_path,
            auto_categorize=auto_categorize,
            overwrite_categories=overwrite,
            check_duplicates=check_duplicates,
            skip_duplicates=skip_duplicates,
            account=account,
        )

        return {
            "success": True,
            "new_transactions": stats["new_transactions"],
            "duplicates_found": stats.get("duplicates_found", 0),
            "categorized": stats.get("categorized", 0),
            "categorization_rate": stats.get("categorization_rate", 0),
            "account": stats.get("account"),
        }
    except Exception as e:
        logger.error(f"Error importing CSV: {e}", exc_info=True)
        return {"success": False, "error": str(e)}


def _filter_by_account(transactions: List[Transaction], account: Optional[str]) -> List[Transaction]:
    if not account:
        return transactions
    needle = account.strip().lower()
    return [t for t in transactions if (t.account or "").strip().lower() == needle]


def get_transactions(page: int = 1, per_page: int = 50, account: Optional[str] = None) -> List[Dict]:
    """
    Get paginated transactions.

    Args:
        page: Page number (1-indexed)
        per_page: Number of transactions per page
        account: Optional account name filter

    Returns:
        List of transaction dictionaries
    """
    if workflow is None:
        init_workflow()

    try:
        transactions = _filter_by_account(workflow.storage.transaction_repo.load_all(), account)
        
        # Sort by date (newest first)
        transactions.sort(key=lambda t: t.date, reverse=True)
        
        # Paginate
        start = (page - 1) * per_page
        end = start + per_page
        page_transactions = transactions[start:end]
        
        # Convert to dictionaries
        result = []
        for txn in page_transactions:
            txn_dict = {
                "id": getattr(txn, "id", None),
                "date": txn.date.isoformat(),
                "description": txn.description,
                "amount": str(txn.amount),
                "transaction_type": txn.transaction_type.value,
                "category": None,
            }
            if txn.category:
                txn_dict["category"] = {
                    "name": txn.category.name,
                    "parent": txn.category.parent,
                }
            if txn.account:
                txn_dict["account"] = txn.account
            if txn.balance is not None:
                txn_dict["balance"] = str(txn.balance)
            
            result.append(txn_dict)
        
        return result
    except Exception as e:
        logger.error(f"Error getting transactions: {e}", exc_info=True)
        return []


def get_overall_stats(account: Optional[str] = None) -> Dict:
    """
    Get overall statistics.

    Returns:
        Dictionary with overall statistics
    """
    if workflow is None:
        init_workflow()

    try:
        transactions = _filter_by_account(workflow.storage.transaction_repo.load_all(), account)
        analyzer = SpendingAnalyzer(transactions)
        total_income = analyzer.get_total_income()
        total_expenses = analyzer.get_total_expenses()
        net_amount = analyzer.get_net_amount()
        
        savings_rate = None
        if total_income > 0:
            savings_rate = float((net_amount / total_income) * 100)
        
        return {
            "total_income": str(total_income),
            "total_expenses": str(total_expenses),
            "net_amount": str(net_amount),
            "savings_rate": savings_rate,
            "account": account,
        }
    except Exception as e:
        logger.error(f"Error getting stats: {e}", exc_info=True)
        return {
            "total_income": "0",
            "total_expenses": "0",
            "net_amount": "0",
            "savings_rate": 0,
            "account": account,
        }


def get_monthly_summaries(account: Optional[str] = None) -> List[Dict]:
    """
    Get all monthly summaries.

    Returns:
        List of monthly summary dictionaries
    """
    if workflow is None:
        init_workflow()

    try:
        transactions = _filter_by_account(workflow.storage.transaction_repo.load_all(), account)
        analyzer = SpendingAnalyzer(transactions)
        summaries = analyzer.get_all_monthly_summaries()
        
        result = []
        for summary in summaries:
            result.append({
                "year": summary.year,
                "month": summary.month,
                "total_income": str(summary.total_income),
                "total_expenses": str(summary.total_expenses),
                "net_amount": str(summary.net_amount),
                "transaction_count": summary.transaction_count,
                "savings_rate": summary.savings_rate,
                "category_breakdown": {
                    k: str(v) for k, v in summary.category_breakdown.items()
                },
            })
        
        return result
    except Exception as e:
        logger.error(f"Error getting monthly summaries: {e}", exc_info=True)
        return []


def get_category_breakdown(account: Optional[str] = None) -> Dict[str, str]:
    """
    Get category breakdown.

    Returns:
        Dictionary mapping category names to total amounts
    """
    if workflow is None:
        init_workflow()

    try:
        transactions = _filter_by_account(workflow.storage.transaction_repo.load_all(), account)
        analyzer = SpendingAnalyzer(transactions)
        breakdown = analyzer.get_category_breakdown()
        return {k: str(v) for k, v in breakdown.items()}
    except Exception as e:
        logger.error(f"Error getting category breakdown: {e}", exc_info=True)
        return {}


def get_spending_patterns() -> List[Dict]:
    """
    Get spending patterns for all categories.

    Returns:
        List of spending pattern dictionaries
    """
    if workflow is None:
        init_workflow()

    try:
        analyzer = workflow.analyze_spending()
        patterns = analyzer.get_spending_patterns()
        
        result = []
        for pattern in patterns:
            result.append({
                "category": pattern.category,
                "total_amount": str(pattern.total_amount),
                "transaction_count": pattern.transaction_count,
                "average_transaction": str(pattern.average_transaction),
                "min_transaction": str(pattern.min_transaction),
                "max_transaction": str(pattern.max_transaction),
                "percentage_of_total": pattern.percentage_of_total,
                "trend": pattern.trend,
            })
        
        # Sort by total amount descending
        result.sort(key=lambda p: float(p["total_amount"]), reverse=True)
        
        return result
    except Exception as e:
        logger.error(f"Error getting spending patterns: {e}", exc_info=True)
        return []


def export_transactions() -> str:
    """
    Export transactions to JSON file.

    Returns:
        Path to exported file
    """
    if workflow is None:
        init_workflow()

    try:
        from datetime import datetime
        
        export_dir = workflow.storage.data_dir / "exports"
        export_dir.mkdir(exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        export_file = export_dir / f"transactions_{timestamp}.json"
        
        workflow.storage.export_transactions_json(export_file)
        
        return str(export_file)
    except Exception as e:
        logger.error(f"Error exporting transactions: {e}", exc_info=True)
        raise


def recategorize_all(overwrite: bool = True) -> Dict:
    """
    Recategorize all transactions.

    Args:
        overwrite: Whether to overwrite existing categories

    Returns:
        Dictionary with recategorization statistics
    """
    if workflow is None:
        init_workflow()

    try:
        stats = workflow.recategorize_all(overwrite=overwrite)
        return {
            "success": True,
            "total": stats["total"],
            "categorized": stats["categorized"],
            "uncategorized": stats["uncategorized"],
            "categorization_rate": stats["categorization_rate"],
        }
    except Exception as e:
        logger.error(f"Error recategorizing: {e}", exc_info=True)
        return {"success": False, "error": str(e)}


# Transaction Editing Endpoints
def edit_transaction(
    transaction_id: str,
    description: Optional[str] = None,
    amount: Optional[str] = None,
    date: Optional[str] = None,
    category_name: Optional[str] = None,
    category_parent: Optional[str] = None,
    notes: Optional[str] = None,
) -> Dict:
    """Edit a transaction."""
    if workflow is None:
        init_workflow()

    try:
        from datetime import datetime
        from decimal import Decimal

        editor = TransactionEditor(workflow.storage.transaction_repo)
        category = None
        if category_name:
            category = Category(name=category_name, parent=category_parent)

        transaction_date = None
        if date:
            transaction_date = datetime.fromisoformat(date).date()

        transaction_amount = None
        if amount:
            transaction_amount = Decimal(amount)

        updated = editor.edit_transaction(
            transaction_id=transaction_id,
            description=description,
            amount=transaction_amount,
            date=transaction_date,
            category=category,
            notes=notes,
        )

        if updated:
            return {"success": True, "transaction": _transaction_to_dict(updated)}
        return {"success": False, "error": "Transaction not found"}
    except Exception as e:
        logger.error(f"Error editing transaction: {e}", exc_info=True)
        return {"success": False, "error": str(e)}


def delete_transaction(transaction_id: str) -> Dict:
    """Delete a transaction."""
    if workflow is None:
        init_workflow()

    try:
        editor = TransactionEditor(workflow.storage.transaction_repo)
        success = editor.delete_transaction(transaction_id)
        return {"success": success}
    except Exception as e:
        logger.error(f"Error deleting transaction: {e}", exc_info=True)
        return {"success": False, "error": str(e)}


def delete_transactions(transaction_ids: List[str]) -> Dict:
    """Delete multiple transactions."""
    if workflow is None:
        init_workflow()

    try:
        editor = TransactionEditor(workflow.storage.transaction_repo)
        count = editor.delete_multiple(transaction_ids)
        return {"success": True, "deleted_count": count}
    except Exception as e:
        logger.error(f"Error deleting transactions: {e}", exc_info=True)
        return {"success": False, "error": str(e)}


def split_transaction(transaction_id: str, splits: List[Dict]) -> Dict:
    """Split a transaction into multiple transactions."""
    if workflow is None:
        init_workflow()

    try:
        from decimal import Decimal

        editor = TransactionEditor(workflow.storage.transaction_repo)
        split_list = []
        for split_data in splits:
            split_list.append(
                SplitTransaction(
                    parent_transaction_id=transaction_id,
                    amount=Decimal(split_data["amount"]),
                    category=Category(
                        name=split_data["category_name"],
                        parent=split_data.get("category_parent"),
                    ),
                    description=split_data.get("description"),
                )
            )

        split_transactions = editor.split_transaction(transaction_id, split_list)
        return {
            "success": True,
            "transactions": [_transaction_to_dict(t) for t in split_transactions],
        }
    except Exception as e:
        logger.error(f"Error splitting transaction: {e}", exc_info=True)
        return {"success": False, "error": str(e)}


def merge_transactions(transaction_ids: List[str], keep_first: bool = True) -> Dict:
    """Merge multiple transactions."""
    if workflow is None:
        init_workflow()

    try:
        editor = TransactionEditor(workflow.storage.transaction_repo)
        merged = editor.merge_transactions(transaction_ids, keep_first)
        if merged:
            return {"success": True, "transaction": _transaction_to_dict(merged)}
        return {"success": False, "error": "Failed to merge"}
    except Exception as e:
        logger.error(f"Error merging transactions: {e}", exc_info=True)
        return {"success": False, "error": str(e)}


def bulk_edit_transactions(
    transaction_ids: List[str], category_name: Optional[str] = None, notes: Optional[str] = None
) -> Dict:
    """Bulk edit transactions."""
    if workflow is None:
        init_workflow()

    try:
        editor = TransactionEditor(workflow.storage.transaction_repo)
        category = None
        if category_name:
            category = Category(name=category_name)

        count = editor.bulk_edit(transaction_ids, category=category, notes=notes)
        return {"success": True, "updated_count": count}
    except Exception as e:
        logger.error(f"Error bulk editing: {e}", exc_info=True)
        return {"success": False, "error": str(e)}


# Search & Filter Endpoints
def search_transactions(
    query: Optional[str] = None,
    category: Optional[str] = None,
    account: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    amount_min: Optional[str] = None,
    amount_max: Optional[str] = None,
    transaction_type: Optional[str] = None,
    is_recurring: Optional[bool] = None,
) -> List[Dict]:
    """Search and filter transactions."""
    if workflow is None:
        init_workflow()

    try:
        from datetime import datetime
        from decimal import Decimal

        transactions = workflow.storage.transaction_repo.load_all()
        searcher = TransactionSearchFilter(transactions)

        date_from_obj = None
        if date_from:
            date_from_obj = datetime.fromisoformat(date_from).date()

        date_to_obj = None
        if date_to:
            date_to_obj = datetime.fromisoformat(date_to).date()

        amount_min_obj = None
        if amount_min:
            amount_min_obj = Decimal(amount_min)

        amount_max_obj = None
        if amount_max:
            amount_max_obj = Decimal(amount_max)

        results = searcher.search(
            query=query,
            category=category,
            account=account,
            date_from=date_from_obj,
            date_to=date_to_obj,
            amount_min=amount_min_obj,
            amount_max=amount_max_obj,
            transaction_type=transaction_type,
            is_recurring=is_recurring,
        )

        return [_transaction_to_dict(t) for t in results]
    except Exception as e:
        logger.error(f"Error searching transactions: {e}", exc_info=True)
        return []


def get_search_filters() -> Dict:
    """Get available filter options."""
    if workflow is None:
        init_workflow()

    try:
        transactions = workflow.storage.transaction_repo.load_all()
        searcher = TransactionSearchFilter(transactions)
        return {
            "categories": searcher.get_categories(),
            "accounts": searcher.get_accounts(),
        }
    except Exception as e:
        logger.error(f"Error getting filters: {e}", exc_info=True)
        return {"categories": [], "accounts": []}


# Budget Tracking Endpoints
def set_budget(
    category_name: str,
    year: int,
    month: int,
    amount: str,
    alert_threshold: str = "0.8",
    notes: Optional[str] = None,
) -> Dict:
    """Set a budget for a category."""
    if workflow is None:
        init_workflow()

    try:
        from decimal import Decimal

        budget_repo = BudgetRepository(workflow.storage.data_dir)
        budget = Budget(
            category_name=category_name,
            year=year,
            month=month,
            amount=Decimal(amount),
            alert_threshold=Decimal(alert_threshold),
            notes=notes,
        )
        budget_repo.save_budget(budget)
        return {"success": True}
    except Exception as e:
        logger.error(f"Error setting budget: {e}", exc_info=True)
        return {"success": False, "error": str(e)}


def get_budget_status(category_name: str, year: int, month: int) -> Dict:
    """Get budget status for a category."""
    if workflow is None:
        init_workflow()

    try:
        transactions = workflow.storage.transaction_repo.load_all()
        budget_repo = BudgetRepository(workflow.storage.data_dir)
        tracker = BudgetTracker(transactions, budget_repo)
        status = tracker.get_budget_status(category_name, year, month)
        return status
    except Exception as e:
        logger.error(f"Error getting budget status: {e}", exc_info=True)
        return {"has_budget": False, "error": str(e)}


def get_all_budget_statuses(year: int, month: int) -> List[Dict]:
    """Get all budget statuses for a month."""
    if workflow is None:
        init_workflow()

    try:
        transactions = workflow.storage.transaction_repo.load_all()
        budget_repo = BudgetRepository(workflow.storage.data_dir)
        tracker = BudgetTracker(transactions, budget_repo)
        return tracker.get_all_budget_statuses(year, month)
    except Exception as e:
        logger.error(f"Error getting budget statuses: {e}", exc_info=True)
        return []


def get_budget_alerts(year: int, month: int) -> List[Dict]:
    """Get budget alerts for a month."""
    if workflow is None:
        init_workflow()

    try:
        transactions = workflow.storage.transaction_repo.load_all()
        budget_repo = BudgetRepository(workflow.storage.data_dir)
        tracker = BudgetTracker(transactions, budget_repo)
        return tracker.check_alerts(year, month)
    except Exception as e:
        logger.error(f"Error getting budget alerts: {e}", exc_info=True)
        return []


def delete_budget(category_name: str, year: int, month: int) -> Dict:
    """Delete a budget."""
    if workflow is None:
        init_workflow()

    try:
        budget_repo = BudgetRepository(workflow.storage.data_dir)
        success = budget_repo.delete_budget(category_name, year, month)
        return {"success": success}
    except Exception as e:
        logger.error(f"Error deleting budget: {e}", exc_info=True)
        return {"success": False, "error": str(e)}


def save_budget_template(name: str, category_budgets: Dict, description: Optional[str] = None) -> Dict:
    """Save a budget template."""
    if workflow is None:
        init_workflow()

    try:
        from decimal import Decimal

        budget_repo = BudgetRepository(workflow.storage.data_dir)
        template = BudgetTemplate(
            name=name,
            category_budgets={k: Decimal(v) for k, v in category_budgets.items()},
            description=description,
        )
        budget_repo.save_template(template)
        return {"success": True}
    except Exception as e:
        logger.error(f"Error saving template: {e}", exc_info=True)
        return {"success": False, "error": str(e)}


def get_budget_templates() -> List[Dict]:
    """Get all budget templates."""
    if workflow is None:
        init_workflow()

    try:
        budget_repo = BudgetRepository(workflow.storage.data_dir)
        templates = budget_repo.load_templates()
        return [
            {
                "name": t.name,
                "category_budgets": {k: str(v) for k, v in t.category_budgets.items()},
                "description": t.description,
            }
            for t in templates
        ]
    except Exception as e:
        logger.error(f"Error getting templates: {e}", exc_info=True)
        return []


# Recurring Transaction Endpoints
def detect_recurring_transactions(min_occurrences: int = 3) -> List[Dict]:
    """Detect recurring transactions."""
    if workflow is None:
        init_workflow()

    try:
        transactions = workflow.storage.transaction_repo.load_all()
        detector = RecurringTransactionDetector(transactions)
        recurring = detector.detect_recurring(min_occurrences)
        return [
            {
                "id": r.id,
                "description_pattern": r.description_pattern,
                "amount": str(r.amount),
                "frequency": r.frequency,
                "confidence": r.confidence,
                "category": r.category.name if r.category else None,
                "account": r.account,
                "last_seen": r.last_seen.isoformat(),
                "next_expected": r.next_expected.isoformat() if r.next_expected else None,
                "transaction_count": r.transaction_count,
            }
            for r in recurring
        ]
    except Exception as e:
        logger.error(f"Error detecting recurring: {e}", exc_info=True)
        return []


def mark_recurring_transactions() -> Dict:
    """Mark transactions as recurring based on detected patterns."""
    if workflow is None:
        init_workflow()

    try:
        transactions = workflow.storage.transaction_repo.load_all()
        detector = RecurringTransactionDetector(transactions)
        recurring = detector.detect_recurring()
        updated = detector.mark_recurring(recurring)
        workflow.storage.transaction_repo._save_all(updated)
        return {"success": True, "marked_count": len([t for t in updated if t.is_recurring])}
    except Exception as e:
        logger.error(f"Error marking recurring: {e}", exc_info=True)
        return {"success": False, "error": str(e)}


# Category Rules Management Endpoints
def get_category_rules() -> List[Dict]:
    """Get all category rules."""
    if workflow is None:
        init_workflow()

    try:
        rules_manager = CategoryRulesManager(workflow.storage.data_dir)
        return rules_manager.get_all_rules()
    except Exception as e:
        logger.error(f"Error getting rules: {e}", exc_info=True)
        return []


def add_category_rule(
    pattern: str,
    category_name: str,
    parent_category: Optional[str] = None,
    case_sensitive: bool = False,
) -> Dict:
    """Add a category rule."""
    if workflow is None:
        init_workflow()

    try:
        rules_manager = CategoryRulesManager(workflow.storage.data_dir)
        success = rules_manager.add_rule(pattern, category_name, parent_category, case_sensitive)
        return {"success": success}
    except Exception as e:
        logger.error(f"Error adding rule: {e}", exc_info=True)
        return {"success": False, "error": str(e)}


def remove_category_rule(pattern: str, category_name: str) -> Dict:
    """Remove a category rule."""
    if workflow is None:
        init_workflow()

    try:
        rules_manager = CategoryRulesManager(workflow.storage.data_dir)
        success = rules_manager.remove_rule(pattern, category_name)
        return {"success": success}
    except Exception as e:
        logger.error(f"Error removing rule: {e}", exc_info=True)
        return {"success": False, "error": str(e)}


def test_category_rule(pattern: str, test_strings: List[str]) -> Dict:
    """Test a category rule pattern."""
    if workflow is None:
        init_workflow()

    try:
        rules_manager = CategoryRulesManager(workflow.storage.data_dir)
        return rules_manager.test_rule(pattern, test_strings)
    except Exception as e:
        logger.error(f"Error testing rule: {e}", exc_info=True)
        return {"valid": False, "error": str(e)}


def test_rule_against_transactions(pattern: str, limit: int = 10) -> List[Dict]:
    """Test rule against existing transactions."""
    if workflow is None:
        init_workflow()

    try:
        transactions = workflow.storage.transaction_repo.load_all()
        rules_manager = CategoryRulesManager(workflow.storage.data_dir)
        return rules_manager.test_against_transactions(pattern, transactions, limit)
    except Exception as e:
        logger.error(f"Error testing rule: {e}", exc_info=True)
        return []


def _transaction_to_dict(transaction) -> Dict:
    """Helper to convert transaction to dictionary."""
    result = {
        "id": transaction.id,
        "date": transaction.date.isoformat(),
        "description": transaction.description,
        "amount": str(transaction.amount),
        "transaction_type": transaction.transaction_type.value,
        "category": None,
        "is_recurring": transaction.is_recurring,
    }
    if transaction.category:
        result["category"] = {
            "name": transaction.category.name,
            "parent": transaction.category.parent,
        }
    if transaction.account:
        result["account"] = transaction.account
    if transaction.notes:
        result["notes"] = transaction.notes
    if transaction.balance is not None:
        result["balance"] = str(transaction.balance)
    return result


def list_accounts() -> List[Dict]:
    if workflow is None:
        init_workflow()
    accounts = workflow.storage.account_repo.ensure_defaults()
    return [a.model_dump() for a in accounts]


def create_account(name: str, account_type: str = "other") -> Dict:
    if workflow is None:
        init_workflow()
    try:
        atype = AccountType(account_type)
    except ValueError:
        atype = AccountType.OTHER
    account = Account(name=name.strip(), account_type=atype)
    saved = workflow.storage.account_repo.upsert(account)
    return {"success": True, "account": saved.model_dump()}


def update_account(account_id: str, name: Optional[str] = None, account_type: Optional[str] = None) -> Dict:
    if workflow is None:
        init_workflow()
    existing = workflow.storage.account_repo.get(account_id)
    if not existing:
        return {"success": False, "error": "Account not found"}
    new_name = name.strip() if name else existing.name
    new_type = existing.account_type
    if account_type:
        try:
            new_type = AccountType(account_type)
        except ValueError:
            pass
    updated = Account(id=existing.id, name=new_name, account_type=new_type)
    # If renamed, retag transactions that used the old name
    if new_name != existing.name:
        txns = workflow.storage.transaction_repo.load_all()
        changed = False
        for i, txn in enumerate(txns):
            if (txn.account or "") == existing.name:
                txns[i] = txn.model_copy(update={"account": new_name})
                changed = True
        if changed:
            workflow.storage.transaction_repo._save_all(txns)
    workflow.storage.account_repo.upsert(updated)
    return {"success": True, "account": updated.model_dump()}


def delete_account(account_id: str) -> Dict:
    if workflow is None:
        init_workflow()
    ok = workflow.storage.account_repo.delete(account_id)
    return {"success": ok}


def assign_account_to_transactions(transaction_ids: List[str], account: str) -> Dict:
    if workflow is None:
        init_workflow()
    txns = workflow.storage.transaction_repo.load_all()
    ids = set(transaction_ids)
    updated = 0
    for i, txn in enumerate(txns):
        if txn.id in ids:
            txns[i] = txn.model_copy(update={"account": account})
            updated += 1
    if updated:
        workflow.storage.transaction_repo._save_all(txns)
    return {"success": True, "updated_count": updated}


def get_credit_card_monthly() -> Dict:
    """Monthly expense breakdown for each credit-card account."""
    from decimal import Decimal

    if workflow is None:
        init_workflow()
    accounts = [
        a for a in workflow.storage.account_repo.ensure_defaults()
        if a.account_type == AccountType.CREDIT_CARD
    ]
    all_txns = workflow.storage.transaction_repo.load_all()
    cards = []
    for account in accounts:
        filtered = _filter_by_account(all_txns, account.name)
        analyzer = SpendingAnalyzer(filtered)
        summaries = analyzer.get_all_monthly_summaries()
        months = [
            {
                "year": s.year,
                "month": s.month,
                "total_expenses": str(s.total_expenses),
                "total_income": str(s.total_income),
                "net_amount": str(s.net_amount),
                "transaction_count": s.transaction_count,
                "category_breakdown": {k: str(v) for k, v in s.category_breakdown.items()},
            }
            for s in summaries
        ]
        total_spend = sum((t.absolute_amount for t in filtered if t.is_expense), Decimal("0"))
        cards.append(
            {
                "account": account.model_dump(),
                "transaction_count": len(filtered),
                "total_expenses": str(total_spend),
                "months": months,
            }
        )
    return {"cards": cards}

