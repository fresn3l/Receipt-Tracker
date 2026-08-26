"""
Budget tracking module for finance tracker.

This module provides budget management functionality including:
- Setting and tracking monthly budgets per category
- Budget vs. spending analysis
- Budget alerts
- Budget templates for quick setup
"""

import json
import logging
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Dict, List, Optional

from banking.analyzer import SpendingAnalyzer
from banking.models import Budget, BudgetTemplate, Transaction
from banking.storage import JSONEncoder

logger = logging.getLogger(__name__)


class BudgetRepository:
    """Repository for managing budget storage."""

    def __init__(self, data_dir: Path):
        """
        Initialize budget repository.

        Args:
            data_dir: Directory where budget data is stored
        """
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.budgets_file = self.data_dir / "budgets.json"
        self.templates_file = self.data_dir / "budget_templates.json"

    def save_budget(self, budget: Budget) -> None:
        """
        Save a budget.

        Args:
            budget: Budget to save
        """
        budgets = self.load_all_budgets()
        # Remove existing budget for same category/month/year
        budgets = [
            b
            for b in budgets
            if not (
                b.category_name == budget.category_name
                and b.year == budget.year
                and b.month == budget.month
            )
        ]
        budgets.append(budget)
        self._save_all_budgets(budgets)

    def load_all_budgets(self) -> List[Budget]:
        """
        Load all budgets.

        Returns:
            List of all budgets
        """
        if not self.budgets_file.exists():
            return []

        try:
            with open(self.budgets_file, "r", encoding="utf-8") as f:
                data = json.load(f)

            budgets = []
            for budget_data in data.get("budgets", []):
                budgets.append(
                    Budget(
                        category_name=budget_data["category_name"],
                        year=budget_data["year"],
                        month=budget_data["month"],
                        amount=Decimal(budget_data["amount"]),
                        alert_threshold=Decimal(budget_data.get("alert_threshold", "0.8")),
                        notes=budget_data.get("notes"),
                    )
                )

            return budgets
        except Exception as e:
            logger.error(f"Error loading budgets: {e}")
            return []

    def get_budget(self, category_name: str, year: int, month: int) -> Optional[Budget]:
        """
        Get budget for a specific category and month.

        Args:
            category_name: Category name
            year: Year
            month: Month (1-12)

        Returns:
            Budget if found, None otherwise
        """
        budgets = self.load_all_budgets()
        for budget in budgets:
            if (
                budget.category_name == category_name
                and budget.year == year
                and budget.month == month
            ):
                return budget
        return None

    def delete_budget(self, category_name: str, year: int, month: int) -> bool:
        """
        Delete a budget.

        Args:
            category_name: Category name
            year: Year
            month: Month

        Returns:
            True if deleted, False if not found
        """
        budgets = self.load_all_budgets()
        original_count = len(budgets)
        budgets = [
            b
            for b in budgets
            if not (
                b.category_name == category_name
                and b.year == year
                and b.month == month
            )
        ]

        if len(budgets) < original_count:
            self._save_all_budgets(budgets)
            return True
        return False

    def _save_all_budgets(self, budgets: List[Budget]) -> None:
        """Save all budgets to file."""
        data = {
            "budgets": [
                {
                    "category_name": b.category_name,
                    "year": b.year,
                    "month": b.month,
                    "amount": str(b.amount),
                    "alert_threshold": str(b.alert_threshold),
                    "notes": b.notes,
                }
                for b in budgets
            ]
        }
        with open(self.budgets_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, cls=JSONEncoder)

    def save_template(self, template: BudgetTemplate) -> None:
        """
        Save a budget template.

        Args:
            template: Template to save
        """
        templates = self.load_templates()
        # Remove existing template with same name
        templates = [t for t in templates if t.name != template.name]
        templates.append(template)
        self._save_templates(templates)

    def load_templates(self) -> List[BudgetTemplate]:
        """
        Load all budget templates.

        Returns:
            List of templates
        """
        if not self.templates_file.exists():
            return []

        try:
            with open(self.templates_file, "r", encoding="utf-8") as f:
                data = json.load(f)

            templates = []
            for template_data in data.get("templates", []):
                templates.append(
                    BudgetTemplate(
                        name=template_data["name"],
                        category_budgets={
                            k: Decimal(v)
                            for k, v in template_data["category_budgets"].items()
                        },
                        description=template_data.get("description"),
                    )
                )

            return templates
        except Exception as e:
            logger.error(f"Error loading templates: {e}")
            return []

    def _save_templates(self, templates: List[BudgetTemplate]) -> None:
        """Save all templates to file."""
        data = {
            "templates": [
                {
                    "name": t.name,
                    "category_budgets": {k: str(v) for k, v in t.category_budgets.items()},
                    "description": t.description,
                }
                for t in templates
            ]
        }
        with open(self.templates_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, cls=JSONEncoder)


class BudgetTracker:
    """Budget tracking and analysis engine."""

    def __init__(
        self, transactions: List[Transaction], budget_repo: BudgetRepository
    ):
        """
        Initialize budget tracker.

        Args:
            transactions: List of transactions to analyze
            budget_repo: Budget repository
        """
        self.transactions = transactions
        self.budget_repo = budget_repo
        self.analyzer = SpendingAnalyzer(transactions)

    def get_budget_status(
        self, category_name: str, year: int, month: int
    ) -> Dict:
        """
        Get budget status for a category and month.

        Args:
            category_name: Category name
            year: Year
            month: Month

        Returns:
            Dictionary with budget status information
        """
        budget = self.budget_repo.get_budget(category_name, year, month)
        if not budget:
            return {"has_budget": False}

        # Get actual spending
        breakdown = self.analyzer.get_category_breakdown(year=year, month=month)
        spent = breakdown.get(category_name, Decimal("0"))

        percentage_spent = float((spent / budget.amount) * 100) if budget.amount > 0 else 0
        remaining = budget.amount - spent
        alert_threshold_amount = budget.amount * budget.alert_threshold

        return {
            "has_budget": True,
            "budget": str(budget.amount),
            "spent": str(spent),
            "remaining": str(remaining),
            "percentage_spent": percentage_spent,
            "alert_threshold": str(alert_threshold_amount),
            "should_alert": spent >= alert_threshold_amount,
            "over_budget": spent > budget.amount,
        }

    def get_all_budget_statuses(self, year: int, month: int) -> List[Dict]:
        """
        Get budget status for all categories with budgets.

        Args:
            year: Year
            month: Month

        Returns:
            List of budget status dictionaries
        """
        budgets = self.budget_repo.load_all_budgets()
        month_budgets = [b for b in budgets if b.year == year and b.month == month]

        statuses = []
        for budget in month_budgets:
            status = self.get_budget_status(budget.category_name, year, month)
            status["category_name"] = budget.category_name
            statuses.append(status)

        return statuses

    def check_alerts(self, year: int, month: int) -> List[Dict]:
        """
        Check for budget alerts.

        Args:
            year: Year
            month: Month

        Returns:
            List of alerts
        """
        statuses = self.get_all_budget_statuses(year, month)
        alerts = []

        for status in statuses:
            if status.get("should_alert"):
                alerts.append(
                    {
                        "category": status["category_name"],
                        "message": f"Budget alert: {status['percentage_spent']:.1f}% of budget spent",
                        "spent": status["spent"],
                        "budget": status["budget"],
                    }
                )
            if status.get("over_budget"):
                alerts.append(
                    {
                        "category": status["category_name"],
                        "message": f"Over budget by ${abs(Decimal(status['remaining']))}",
                        "spent": status["spent"],
                        "budget": status["budget"],
                    }
                )

        return alerts

