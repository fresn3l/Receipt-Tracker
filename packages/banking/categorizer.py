"""
Transaction categorization engine.

This module provides the categorization engine that applies category mappings to
transactions. It integrates with CategoryMapper to automatically categorize
transactions and provides statistics on categorization success.

Features:
    - Batch and single transaction categorization
    - Option to overwrite or preserve existing categories
    - Statistics tracking (success rate, categorized count, etc.)
    - Filtering methods (uncategorized, by category, etc.)
    - Manual categorization support

Example:
    >>> from banking.categorizer import TransactionCategorizer
    >>> from banking.models import Transaction, TransactionType
    >>> 
    >>> categorizer = TransactionCategorizer()
    >>> transaction = Transaction(...)  # Uncategorized transaction
    >>> categorized = categorizer.categorize_transaction(transaction)
    >>> 
    >>> # Batch categorization
    >>> transactions = [transaction1, transaction2, ...]
    >>> categorized, stats = categorizer.categorize_transactions(transactions)
    >>> print(f"Categorized {stats.categorized_count}/{stats.total_transactions}")
    >>> print(f"Success rate: {stats.categorization_rate:.1f}%")
"""

from typing import List, Optional

from banking.category_mapper import CategoryMapper, get_default_mapper
from banking.models import Category, Transaction


class CategorizationStats:
    """Statistics about categorization results."""

    def __init__(self):
        """Initialize empty stats."""
        self.total_transactions = 0
        self.categorized_count = 0
        self.uncategorized_count = 0
        self.already_categorized_count = 0
        self.newly_categorized_count = 0

    @property
    def categorization_rate(self) -> float:
        """Calculate categorization success rate."""
        if self.total_transactions == 0:
            return 0.0
        return (self.categorized_count / self.total_transactions) * 100.0

    def __repr__(self) -> str:
        """String representation of stats."""
        return (
            f"CategorizationStats(total={self.total_transactions}, "
            f"categorized={self.categorized_count}, "
            f"uncategorized={self.uncategorized_count}, "
            f"rate={self.categorization_rate:.1f}%)"
        )


class TransactionCategorizer:
    """Engine for categorizing transactions."""

    def __init__(self, mapper: Optional[CategoryMapper] = None):
        """
        Initialize transaction categorizer.

        Args:
            mapper: Optional CategoryMapper instance. If None, uses default mapper.
        """
        self.mapper = mapper if mapper is not None else get_default_mapper()

    def categorize_transaction(
        self, transaction: Transaction, overwrite: bool = False
    ) -> Transaction:
        """
        Categorize a single transaction.

        Args:
            transaction: Transaction to categorize
            overwrite: If True, overwrite existing category. If False, skip if already categorized.

        Returns:
            Transaction with category assigned (if match found)
        """
        # Skip if already categorized and not overwriting
        if transaction.category is not None and not overwrite:
            return transaction

        # Try to categorize based on description
        category = self.mapper.categorize(transaction.description)

        if category:
            # Create new transaction with category
            return Transaction(
                date=transaction.date,
                amount=transaction.amount,
                description=transaction.description,
                category=category,
                transaction_type=transaction.transaction_type,
                account=transaction.account,
                reference=transaction.reference,
                balance=transaction.balance,
                notes=transaction.notes,
            )

        return transaction

    def categorize_transactions(
        self, transactions: List[Transaction], overwrite: bool = False
    ) -> tuple[List[Transaction], CategorizationStats]:
        """
        Categorize a list of transactions.

        Args:
            transactions: List of transactions to categorize
            overwrite: If True, overwrite existing categories. If False, skip if already categorized.

        Returns:
            Tuple of (categorized transactions, statistics)
        """
        categorized_transactions = []
        stats = CategorizationStats()
        stats.total_transactions = len(transactions)

        for transaction in transactions:
            # Check if already categorized
            was_categorized = transaction.category is not None

            # Categorize transaction
            categorized = self.categorize_transaction(transaction, overwrite=overwrite)

            # Update statistics
            if categorized.category is not None:
                stats.categorized_count += 1
                if was_categorized:
                    stats.already_categorized_count += 1
                else:
                    stats.newly_categorized_count += 1
            else:
                stats.uncategorized_count += 1

            categorized_transactions.append(categorized)

        return categorized_transactions, stats

    def categorize_by_category_name(
        self, transactions: List[Transaction], category_name: str, parent_category: Optional[str] = None
    ) -> List[Transaction]:
        """
        Manually assign a category to transactions.

        Args:
            transactions: List of transactions to categorize
            category_name: Name of the category to assign
            parent_category: Optional parent category name

        Returns:
            List of transactions with category assigned
        """
        category = Category(name=category_name, parent=parent_category, description=None)
        categorized = []

        for transaction in transactions:
            categorized_transaction = Transaction(
                date=transaction.date,
                amount=transaction.amount,
                description=transaction.description,
                category=category,
                transaction_type=transaction.transaction_type,
                account=transaction.account,
                reference=transaction.reference,
                balance=transaction.balance,
                notes=transaction.notes,
            )
            categorized.append(categorized_transaction)

        return categorized

    def get_uncategorized_transactions(self, transactions: List[Transaction]) -> List[Transaction]:
        """
        Get list of transactions that don't have a category.

        Args:
            transactions: List of transactions to filter

        Returns:
            List of uncategorized transactions
        """
        return [t for t in transactions if t.category is None]

    def get_categorized_transactions(self, transactions: List[Transaction]) -> List[Transaction]:
        """
        Get list of transactions that have a category.

        Args:
            transactions: List of transactions to filter

        Returns:
            List of categorized transactions
        """
        return [t for t in transactions if t.category is not None]

    def get_transactions_by_category(
        self, transactions: List[Transaction], category_name: str
    ) -> List[Transaction]:
        """
        Get transactions filtered by category name.

        Args:
            transactions: List of transactions to filter
            category_name: Name of category to filter by

        Returns:
            List of transactions in the specified category
        """
        return [
            t for t in transactions if t.category is not None and t.category.name == category_name
        ]


def categorize_transactions(
    transactions: List[Transaction], overwrite: bool = False, mapper: Optional[CategoryMapper] = None
) -> tuple[List[Transaction], CategorizationStats]:
    """
    Convenience function to categorize transactions.

    Args:
        transactions: List of transactions to categorize
        overwrite: If True, overwrite existing categories
        mapper: Optional CategoryMapper instance

    Returns:
        Tuple of (categorized transactions, statistics)
    """
    categorizer = TransactionCategorizer(mapper=mapper)
    return categorizer.categorize_transactions(transactions, overwrite=overwrite)

