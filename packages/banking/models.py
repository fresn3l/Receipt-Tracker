"""
Data models for finance tracker application.

This module defines the core data structures used throughout the application:
- TransactionType: Enumeration of transaction types
- Category: Spending categories with hierarchical support
- Transaction: Individual financial transactions
- MonthlySummary: Aggregated monthly statistics
- SpendingPattern: Category-level spending analysis

All models use Pydantic v2 for validation, serialization, and type safety.
Monetary values use Decimal to avoid floating-point precision issues.

Example:
    >>> from banking.models import Transaction, TransactionType, Category
    >>> from datetime import date
    >>> from decimal import Decimal
    >>> 
    >>> category = Category(name="Groceries", parent="Food & Dining")
    >>> transaction = Transaction(
    ...     date=date(2024, 1, 15),
    ...     amount=Decimal("-50.00"),
    ...     description="Grocery Store",
    ...     transaction_type=TransactionType.DEBIT,
    ...     category=category
    ... )
    >>> print(transaction.is_expense)
    True
"""

from __future__ import annotations

import datetime
from decimal import Decimal
from enum import Enum
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


class TransactionType(str, Enum):
    """Enumeration of transaction types."""

    DEBIT = "debit"  # Money going out
    CREDIT = "credit"  # Money coming in
    TRANSFER = "transfer"  # Internal transfer


class Category(BaseModel):
    """Represents a spending category."""

    name: str = Field(..., description="Category name (e.g., 'Groceries', 'Transportation')")
    parent: Optional[str] = Field(
        None, description="Parent category name for hierarchical categorization"
    )
    description: Optional[str] = Field(None, description="Optional category description")

    model_config = ConfigDict(frozen=True)  # Make categories immutable


class Transaction(BaseModel):
    """Represents a single financial transaction."""

    date: datetime.date = Field(..., description="Transaction date")
    amount: Decimal = Field(..., description="Transaction amount (positive for credits, negative for debits)")
    description: str = Field(..., description="Transaction description/merchant name")
    category: Optional[Category] = Field(None, description="Assigned category")
    transaction_type: TransactionType = Field(..., description="Type of transaction")
    account: Optional[str] = Field(None, description="Account identifier")
    reference: Optional[str] = Field(None, description="Transaction reference number")
    balance: Optional[Decimal] = Field(None, description="Account balance after transaction")
    notes: Optional[str] = Field(None, description="User-added notes")
    id: Optional[str] = Field(None, description="Unique transaction identifier")
    is_recurring: bool = Field(default=False, description="Whether this is a recurring transaction")
    recurring_id: Optional[str] = Field(None, description="ID of recurring transaction group")
    parent_transaction_id: Optional[str] = Field(None, description="ID of parent transaction if this is a split")
    id: Optional[str] = Field(None, description="Unique transaction identifier")
    is_recurring: bool = Field(default=False, description="Whether this is a recurring transaction")
    recurring_id: Optional[str] = Field(None, description="ID of recurring transaction group")
    parent_transaction_id: Optional[str] = Field(None, description="ID of parent transaction if this is a split")

    @field_validator("amount")
    @classmethod
    def validate_amount(cls, v: Decimal) -> Decimal:
        """Ensure amount is not zero."""
        if v == 0:
            raise ValueError("Transaction amount cannot be zero")
        return v

    @property
    def is_expense(self) -> bool:
        """Check if transaction is an expense (debit)."""
        return self.transaction_type == TransactionType.DEBIT or (
            self.transaction_type == TransactionType.TRANSFER and self.amount < 0
        )

    @property
    def is_income(self) -> bool:
        """Check if transaction is income (credit)."""
        return self.transaction_type == TransactionType.CREDIT or (
            self.transaction_type == TransactionType.TRANSFER and self.amount > 0
        )

    @property
    def absolute_amount(self) -> Decimal:
        """Get absolute value of transaction amount."""
        return abs(self.amount)

    model_config = ConfigDict(
        json_encoders={
            Decimal: str,
            datetime.date: lambda v: v.isoformat(),
        }
    )


class MonthlySummary(BaseModel):
    """Summary of transactions for a specific month."""

    year: int = Field(..., description="Year")
    month: int = Field(..., ge=1, le=12, description="Month (1-12)")
    total_income: Decimal = Field(default=Decimal("0"), description="Total income for the month")
    total_expenses: Decimal = Field(default=Decimal("0"), description="Total expenses for the month")
    net_amount: Decimal = Field(default=Decimal("0"), description="Net amount (income - expenses)")
    transaction_count: int = Field(default=0, description="Number of transactions")
    category_breakdown: dict[str, Decimal] = Field(
        default_factory=dict, description="Expenses by category"
    )

    @property
    def savings_rate(self) -> Optional[float]:
        """Calculate savings rate as percentage."""
        if self.total_income == 0:
            return None
        return float((self.net_amount / self.total_income) * 100)

    model_config = ConfigDict(
        json_encoders={
            Decimal: str,
        }
    )


class SpendingPattern(BaseModel):
    """Represents spending patterns and trends."""

    category: str = Field(..., description="Category name")
    total_amount: Decimal = Field(..., description="Total spending in this category")
    transaction_count: int = Field(..., description="Number of transactions")
    average_transaction: Decimal = Field(..., description="Average transaction amount")
    min_transaction: Decimal = Field(..., description="Minimum transaction amount")
    max_transaction: Decimal = Field(..., description="Maximum transaction amount")
    percentage_of_total: Optional[float] = Field(
        None, description="Percentage of total spending"
    )
    trend: Optional[str] = Field(
        None, description="Trend direction (increasing, decreasing, stable)"
    )

    model_config = ConfigDict(
        json_encoders={
            Decimal: str,
        }
    )


class Budget(BaseModel):
    """Represents a monthly budget for a category."""

    category_name: str = Field(..., description="Category name")
    year: int = Field(..., description="Budget year")
    month: int = Field(..., ge=1, le=12, description="Budget month (1-12)")
    amount: Decimal = Field(..., description="Budget amount")
    alert_threshold: Decimal = Field(
        default=Decimal("0.8"), description="Alert when spending reaches this percentage (0-1)"
    )
    notes: Optional[str] = Field(None, description="Budget notes")

    model_config = ConfigDict(
        json_encoders={
            Decimal: str,
        }
    )


class BudgetTemplate(BaseModel):
    """Template for quick budget setup."""

    name: str = Field(..., description="Template name")
    category_budgets: dict[str, Decimal] = Field(
        ..., description="Category name to budget amount mapping"
    )
    description: Optional[str] = Field(None, description="Template description")

    model_config = ConfigDict(
        json_encoders={
            Decimal: str,
        }
    )


class RecurringTransaction(BaseModel):
    """Represents a detected recurring transaction pattern."""

    id: str = Field(..., description="Unique recurring transaction ID")
    description_pattern: str = Field(..., description="Pattern matching transaction descriptions")
    amount: Decimal = Field(..., description="Typical transaction amount")
    frequency: str = Field(..., description="Frequency: monthly, weekly, yearly")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence score (0-1)")
    category: Optional[Category] = Field(None, description="Assigned category")
    account: Optional[str] = Field(None, description="Account identifier")
    last_seen: datetime.date = Field(..., description="Date of last occurrence")
    next_expected: Optional[datetime.date] = Field(None, description="Expected next occurrence")
    transaction_count: int = Field(default=0, description="Number of matching transactions")
    amount_variance: Optional[Decimal] = Field(None, description="Amount variance if variable")

    model_config = ConfigDict(
        json_encoders={
            Decimal: str,
        }
    )


class SplitTransaction(BaseModel):
    """Represents a split of a transaction into multiple categories."""

    parent_transaction_id: str = Field(..., description="ID of parent transaction")
    amount: Decimal = Field(..., description="Amount for this split")
    category: Category = Field(..., description="Category for this split")
    description: Optional[str] = Field(None, description="Split description/notes")

    model_config = ConfigDict(
        json_encoders={
            Decimal: str,
        }
    )

