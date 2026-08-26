"""
Recurring transaction detection module.

This module automatically detects recurring transactions (subscriptions, bills, etc.)
by analyzing transaction patterns.
"""

import logging
import re
import uuid
from collections import defaultdict
from datetime import date, timedelta
from decimal import Decimal
from typing import Dict, List, Optional

from banking.models import Category, RecurringTransaction, Transaction

logger = logging.getLogger(__name__)


class RecurringTransactionDetector:
    """Detects recurring transaction patterns."""

    def __init__(self, transactions: List[Transaction]):
        """
        Initialize detector.

        Args:
            transactions: List of transactions to analyze
        """
        self.transactions = transactions

    def detect_recurring(self, min_occurrences: int = 3) -> List[RecurringTransaction]:
        """
        Detect recurring transactions.

        Args:
            min_occurrences: Minimum number of occurrences to consider recurring

        Returns:
            List of detected recurring transactions
        """
        # Group transactions by description pattern
        description_groups = defaultdict(list)
        for transaction in self.transactions:
            # Normalize description for grouping
            pattern = self._normalize_description(transaction.description)
            description_groups[pattern].append(transaction)

        recurring = []
        for pattern, group_transactions in description_groups.items():
            if len(group_transactions) < min_occurrences:
                continue

            # Analyze frequency
            frequency_info = self._analyze_frequency(group_transactions)
            if not frequency_info:
                continue

            # Calculate confidence
            confidence = self._calculate_confidence(group_transactions, frequency_info)

            # Get representative transaction
            representative = group_transactions[0]

            # Calculate amount statistics
            amounts = [abs(t.amount) for t in group_transactions]
            avg_amount = sum(amounts) / len(amounts)
            amount_variance = max(amounts) - min(amounts) if len(amounts) > 1 else None

            recurring.append(
                RecurringTransaction(
                    id=str(uuid.uuid4()),
                    description_pattern=pattern,
                    amount=Decimal(str(avg_amount)),
                    frequency=frequency_info["frequency"],
                    confidence=confidence,
                    category=representative.category,
                    account=representative.account,
                    last_seen=max(t.date for t in group_transactions),
                    next_expected=self._predict_next(
                        max(t.date for t in group_transactions), frequency_info["frequency"]
                    ),
                    transaction_count=len(group_transactions),
                    amount_variance=Decimal(str(amount_variance)) if amount_variance else None,
                )
            )

        return sorted(recurring, key=lambda x: x.confidence, reverse=True)

    def _normalize_description(self, description: str) -> str:
        """
        Normalize transaction description for pattern matching.

        Args:
            description: Original description

        Returns:
            Normalized description pattern
        """
        # Remove common variable parts (dates, transaction IDs, etc.)
        normalized = description.lower().strip()
        # Remove numbers that might be transaction IDs
        normalized = re.sub(r"\d{4,}", "", normalized)
        # Remove common suffixes
        normalized = re.sub(r"\s+(inc|llc|ltd|corp)\.?$", "", normalized)
        # Remove extra whitespace
        normalized = " ".join(normalized.split())
        return normalized

    def _analyze_frequency(self, transactions: List[Transaction]) -> Optional[Dict]:
        """
        Analyze frequency of transactions.

        Args:
            transactions: List of transactions

        Returns:
            Dictionary with frequency information or None
        """
        if len(transactions) < 2:
            return None

        dates = sorted([t.date for t in transactions])
        intervals = [
            (dates[i + 1] - dates[i]).days for i in range(len(dates) - 1)
        ]

        if not intervals:
            return None

        avg_interval = sum(intervals) / len(intervals)

        # Determine frequency
        if 25 <= avg_interval <= 35:
            frequency = "monthly"
        elif 6 <= avg_interval <= 8:
            frequency = "weekly"
        elif 360 <= avg_interval <= 370:
            frequency = "yearly"
        else:
            # Not a clear pattern
            return None

        return {"frequency": frequency, "avg_interval": avg_interval}

    def _calculate_confidence(
        self, transactions: List[Transaction], frequency_info: Dict
    ) -> float:
        """
        Calculate confidence score for recurring transaction.

        Args:
            transactions: List of transactions
            frequency_info: Frequency analysis results

        Returns:
            Confidence score (0-1)
        """
        # Base confidence on number of occurrences
        occurrence_score = min(len(transactions) / 10.0, 1.0)

        # Check amount consistency
        amounts = [abs(t.amount) for t in transactions]
        if amounts:
            amount_variance = (max(amounts) - min(amounts)) / max(amounts) if max(amounts) > 0 else 1.0
            consistency_score = max(0, 1.0 - amount_variance)
        else:
            consistency_score = 0.5

        # Check date regularity
        dates = sorted([t.date for t in transactions])
        intervals = [
            (dates[i + 1] - dates[i]).days for i in range(len(dates) - 1)
        ]
        if intervals:
            interval_variance = (
                (max(intervals) - min(intervals)) / max(intervals)
                if max(intervals) > 0
                else 0
            )
            regularity_score = max(0, 1.0 - interval_variance)
        else:
            regularity_score = 0.5

        # Weighted average
        confidence = (
            occurrence_score * 0.4 + consistency_score * 0.3 + regularity_score * 0.3
        )

        return min(1.0, max(0.0, confidence))

    def _predict_next(self, last_date: date, frequency: str) -> date:
        """
        Predict next occurrence date.

        Args:
            last_date: Last occurrence date
            frequency: Frequency (monthly, weekly, yearly)

        Returns:
            Predicted next date
        """
        if frequency == "monthly":
            # Add approximately 30 days
            return last_date + timedelta(days=30)
        elif frequency == "weekly":
            return last_date + timedelta(days=7)
        elif frequency == "yearly":
            return last_date + timedelta(days=365)
        else:
            return last_date + timedelta(days=30)

    def mark_recurring(self, recurring_transactions: List[RecurringTransaction]) -> List[Transaction]:
        """
        Mark transactions as recurring based on detected patterns.

        Args:
            recurring_transactions: List of detected recurring patterns

        Returns:
            Updated list of transactions with recurring flags
        """
        updated_transactions = []
        pattern_map = {rt.description_pattern: rt for rt in recurring_transactions}

        for transaction in self.transactions:
            pattern = self._normalize_description(transaction.description)
            if pattern in pattern_map:
                recurring = pattern_map[pattern]
                # Create updated transaction with recurring info
                updated = Transaction(
                    **transaction.model_dump(),
                    is_recurring=True,
                    recurring_id=recurring.id,
                )
                updated_transactions.append(updated)
            else:
                updated_transactions.append(transaction)

        return updated_transactions

