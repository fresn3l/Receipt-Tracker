"""
Advanced search and filtering module for transactions.

This module provides powerful search and filtering capabilities for transactions.
"""

import logging
from datetime import date
from decimal import Decimal
from typing import Callable, Dict, List, Optional

from banking.models import Transaction

logger = logging.getLogger(__name__)


class TransactionSearchFilter:
    """Advanced search and filter for transactions."""

    def __init__(self, transactions: List[Transaction]):
        """
        Initialize search filter.

        Args:
            transactions: List of transactions to search/filter
        """
        self.transactions = transactions

    def search(
        self,
        query: Optional[str] = None,
        category: Optional[str] = None,
        account: Optional[str] = None,
        date_from: Optional[date] = None,
        date_to: Optional[date] = None,
        amount_min: Optional[Decimal] = None,
        amount_max: Optional[Decimal] = None,
        transaction_type: Optional[str] = None,
        is_recurring: Optional[bool] = None,
    ) -> List[Transaction]:
        """
        Search and filter transactions.

        Args:
            query: Text search in description
            category: Filter by category name
            account: Filter by account
            date_from: Start date (inclusive)
            date_to: End date (inclusive)
            amount_min: Minimum amount (absolute value)
            amount_max: Maximum amount (absolute value)
            transaction_type: Filter by type (debit, credit, transfer)
            is_recurring: Filter by recurring status

        Returns:
            Filtered list of transactions
        """
        results = self.transactions

        # Text search
        if query:
            query_lower = query.lower()
            results = [
                t
                for t in results
                if query_lower in t.description.lower()
                or (t.notes and query_lower in t.notes.lower())
            ]

        # Category filter
        if category:
            results = [
                t
                for t in results
                if t.category and t.category.name.lower() == category.lower()
            ]

        # Account filter
        if account:
            results = [t for t in results if t.account and t.account == account]

        # Date range filter
        if date_from:
            results = [t for t in results if t.date >= date_from]
        if date_to:
            results = [t for t in results if t.date <= date_to]

        # Amount range filter
        if amount_min is not None:
            results = [
                t for t in results if abs(t.amount) >= abs(amount_min)
            ]
        if amount_max is not None:
            results = [
                t for t in results if abs(t.amount) <= abs(amount_max)
            ]

        # Transaction type filter
        if transaction_type:
            results = [
                t
                for t in results
                if t.transaction_type.value.lower() == transaction_type.lower()
            ]

        # Recurring filter
        if is_recurring is not None:
            results = [t for t in results if t.is_recurring == is_recurring]

        return results

    def advanced_query(self, query_dict: Dict) -> List[Transaction]:
        """
        Execute advanced query from dictionary.

        Args:
            query_dict: Dictionary with query parameters

        Returns:
            Filtered transactions
        """
        return self.search(
            query=query_dict.get("query"),
            category=query_dict.get("category"),
            account=query_dict.get("account"),
            date_from=query_dict.get("date_from"),
            date_to=query_dict.get("date_to"),
            amount_min=query_dict.get("amount_min"),
            amount_max=query_dict.get("amount_max"),
            transaction_type=query_dict.get("transaction_type"),
            is_recurring=query_dict.get("is_recurring"),
        )

    def get_categories(self) -> List[str]:
        """
        Get list of all unique categories.

        Returns:
            List of category names
        """
        categories = set()
        for transaction in self.transactions:
            if transaction.category:
                categories.add(transaction.category.name)
        return sorted(list(categories))

    def get_accounts(self) -> List[str]:
        """
        Get list of all unique accounts.

        Returns:
            List of account names
        """
        accounts = set()
        for transaction in self.transactions:
            if transaction.account:
                accounts.add(transaction.account)
        return sorted(list(accounts))

