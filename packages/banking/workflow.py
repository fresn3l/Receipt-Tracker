"""
End-to-end workflow for processing CSV files.

This module provides the main workflow orchestrator that combines all components
to process CSV files from start to finish: parsing, categorization, analysis, and storage.

The FinanceTrackerWorkflow class provides a high-level interface that:
    1. Parses CSV files into Transaction objects
    2. Detects and handles duplicate transactions
    3. Automatically categorizes transactions
    4. Saves transactions to persistent storage
    5. Provides analysis capabilities

This is the recommended way to use the finance tracker programmatically.

Example:
    >>> from banking.workflow import FinanceTrackerWorkflow
    >>> from pathlib import Path
    >>> 
    >>> workflow = FinanceTrackerWorkflow()
    >>> 
    >>> # Process a CSV file
    >>> transactions, stats = workflow.process_csv_file(
    ...     Path("bank_statement.csv"),
    ...     auto_categorize=True,
    ...     check_duplicates=True
    ... )
    >>> 
    >>> print(f"Imported {stats['new_transactions']} transactions")
    >>> print(f"Categorized: {stats.get('categorized', 0)}")
    >>> 
    >>> # Analyze spending
    >>> analyzer = workflow.analyze_spending()
    >>> summary = analyzer.get_monthly_summary(2024, 1)
    >>> 
    >>> # Get uncategorized transactions
    >>> uncategorized = workflow.get_uncategorized_transactions()
"""

import logging
from pathlib import Path
from typing import List, Optional

from banking.analyzer import SpendingAnalyzer
from banking.categorizer import TransactionCategorizer, categorize_transactions
from banking.csv_parser import CSVParser, parse_csv
from banking.models import Transaction
from banking.storage import StorageManager

logger = logging.getLogger(__name__)


class FinanceTrackerWorkflow:
    """End-to-end workflow for processing financial transactions."""

    def __init__(self, data_dir: Optional[Path] = None, account: Optional[str] = None):
        """
        Initialize workflow.

        Args:
            data_dir: Optional data directory
            account: Optional account identifier
        """
        self.storage = StorageManager(data_dir)
        self.account = account
        self.parser = CSVParser(account=account)
        self.categorizer = TransactionCategorizer()

    def process_csv_file(
        self,
        csv_file: Path,
        auto_categorize: bool = True,
        overwrite_categories: bool = False,
        check_duplicates: bool = True,
        skip_duplicates: bool = True,
    ) -> tuple[List[Transaction], dict]:
        """
        Process a CSV file: parse, categorize, and store.

        Args:
            csv_file: Path to CSV file
            auto_categorize: Whether to automatically categorize transactions
            overwrite_categories: Whether to overwrite existing categories
            check_duplicates: Whether to check for duplicates
            skip_duplicates: Whether to skip duplicate transactions

        Returns:
            Tuple of (processed transactions, statistics dict)
        """
        logger.info(f"Processing CSV file: {csv_file}")

        # Parse CSV
        logger.info("Parsing CSV file...")
        transactions = self.parser.parse(csv_file)
        logger.info(f"Parsed {len(transactions)} transactions")

        # Check for duplicates
        duplicates = []
        if check_duplicates:
            duplicates = self.storage.transaction_repo.check_duplicates(transactions)
            if duplicates:
                logger.warning(f"Found {len(duplicates)} duplicate transactions")
                if skip_duplicates:
                    # Create a helper function to get transaction ID
                    def get_txn_id(t):
                        parts = [
                            t.date.isoformat(),
                            str(t.amount),
                            t.description.strip().lower(),
                        ]
                        if t.reference:
                            parts.append(t.reference)
                        return "|".join(parts)

                    transaction_ids = {get_txn_id(t) for t in duplicates}
                    transactions = [
                        t for t in transactions if get_txn_id(t) not in transaction_ids
                    ]
                    logger.info(f"Skipped {len(duplicates)} duplicates, processing {len(transactions)} new transactions")

        # Categorize transactions
        if auto_categorize:
            logger.info("Categorizing transactions...")
            transactions, stats = self.categorizer.categorize_transactions(
                transactions, overwrite=overwrite_categories
            )
            logger.info(
                f"Categorized {stats.categorized_count}/{stats.total_transactions} "
                f"transactions ({stats.categorization_rate:.1f}%)"
            )
        else:
            stats = None

        # Save to storage
        logger.info("Saving transactions to storage...")
        self.storage.transaction_repo.save(transactions)
        logger.info(f"Saved {len(transactions)} transactions")

        # Prepare statistics
        result_stats = {
            "total_parsed": len(transactions) + len(duplicates),
            "new_transactions": len(transactions),
            "duplicates_found": len(duplicates),
            "duplicates_skipped": len(duplicates) if skip_duplicates else 0,
        }

        if stats:
            result_stats.update(
                {
                    "categorized": stats.categorized_count,
                    "uncategorized": stats.uncategorized_count,
                    "categorization_rate": stats.categorization_rate,
                }
            )

        return transactions, result_stats

    def analyze_spending(
        self, year: Optional[int] = None, month: Optional[int] = None
    ) -> SpendingAnalyzer:
        """
        Analyze spending from stored transactions.

        Args:
            year: Optional year to filter by
            month: Optional month to filter by (requires year)

        Returns:
            SpendingAnalyzer instance
        """
        transactions = self.storage.transaction_repo.load_all()
        analyzer = SpendingAnalyzer(transactions)
        return analyzer

    def get_uncategorized_transactions(self) -> List[Transaction]:
        """Get all uncategorized transactions from storage."""
        transactions = self.storage.transaction_repo.load_all()
        return self.categorizer.get_uncategorized_transactions(transactions)

    def recategorize_all(self, overwrite: bool = True) -> dict:
        """
        Recategorize all stored transactions.

        Args:
            overwrite: Whether to overwrite existing categories

        Returns:
            Statistics dictionary
        """
        logger.info("Recategorizing all transactions...")
        transactions = self.storage.transaction_repo.load_all()
        categorized, stats = self.categorizer.categorize_transactions(transactions, overwrite=overwrite)

        # Save recategorized transactions
        self.storage.transaction_repo.save(categorized)

        return {
            "total": stats.total_transactions,
            "categorized": stats.categorized_count,
            "uncategorized": stats.uncategorized_count,
            "categorization_rate": stats.categorization_rate,
        }


def process_csv(
    csv_file: Path,
    data_dir: Optional[Path] = None,
    account: Optional[str] = None,
    auto_categorize: bool = True,
) -> tuple[List[Transaction], dict]:
    """
    Convenience function to process a CSV file.

    Args:
        csv_file: Path to CSV file
        data_dir: Optional data directory
        account: Optional account identifier
        auto_categorize: Whether to automatically categorize

    Returns:
        Tuple of (processed transactions, statistics)
    """
    workflow = FinanceTrackerWorkflow(data_dir=data_dir, account=account)
    return workflow.process_csv_file(csv_file, auto_categorize=auto_categorize)

