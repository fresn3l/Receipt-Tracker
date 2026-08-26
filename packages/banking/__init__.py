"""
Finance Tracker - A comprehensive tool for tracking and categorizing financial transactions.

This package provides functionality to:
- Parse bank statement CSV files in multiple formats
- Automatically categorize transactions using pattern matching
- Analyze spending patterns and generate reports
- Store and manage transaction data
- Provide both CLI and web interfaces

Main Components:
- models: Data models for transactions, categories, and summaries
- csv_parser: CSV file parsing and format detection
- category_mapper: Automatic categorization using rules
- categorizer: Transaction categorization engine
- analyzer: Spending analysis and reporting
- storage: Data persistence layer
- workflow: End-to-end processing workflows
- cli: Command-line interface
- web_app: Web application interface

Example Usage:
    >>> from banking.workflow import FinanceTrackerWorkflow
    >>> workflow = FinanceTrackerWorkflow()
    >>> transactions, stats = workflow.process_csv_file("bank_statement.csv")
    >>> print(f"Imported {stats['new_transactions']} transactions")
"""

__version__ = "0.1.0"

# Core models
from banking.models import (
    Category,
    MonthlySummary,
    SpendingPattern,
    Transaction,
    TransactionType,
)

# Main workflow
from banking.workflow import FinanceTrackerWorkflow, process_csv

# Convenience imports
from banking.analyzer import SpendingAnalyzer, analyze_spending
from banking.categorizer import (
    CategorizationStats,
    TransactionCategorizer,
    categorize_transactions,
)
from banking.csv_parser import CSVParser, CSVFormat, parse_csv
from banking.storage import StorageManager

__all__ = [
    # Version
    "__version__",
    # Models
    "Transaction",
    "Category",
    "TransactionType",
    "MonthlySummary",
    "SpendingPattern",
    # Parsing
    "CSVParser",
    "CSVFormat",
    "parse_csv",
    # Categorization
    "CategoryMapper",
    "TransactionCategorizer",
    "CategorizationStats",
    "categorize_transactions",
    # Analysis
    "SpendingAnalyzer",
    "analyze_spending",
    # Storage
    "StorageManager",
    # Workflow
    "FinanceTrackerWorkflow",
    "process_csv",
]

# Lazy import for category_mapper to avoid circular dependencies if needed
def __getattr__(name: str):
    if name == "CategoryMapper":
        from banking.category_mapper import CategoryMapper
        return CategoryMapper
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
