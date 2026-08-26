"""
Transaction editing and management module.

This module provides functionality to edit, delete, split, and merge transactions.
"""

import logging
import uuid
from decimal import Decimal
from typing import Dict, List, Optional

from banking.models import Category, SplitTransaction, Transaction

logger = logging.getLogger(__name__)


class TransactionEditor:
    """Transaction editing and management."""

    def __init__(self, transaction_repo):
        """
        Initialize transaction editor.

        Args:
            transaction_repo: TransactionRepository instance
        """
        self.repo = transaction_repo

    def edit_transaction(
        self,
        transaction_id: str,
        description: Optional[str] = None,
        amount: Optional[Decimal] = None,
        date: Optional = None,
        category: Optional[Category] = None,
        notes: Optional[str] = None,
    ) -> Optional[Transaction]:
        """
        Edit a transaction.

        Args:
            transaction_id: Transaction ID
            description: New description (optional)
            amount: New amount (optional)
            date: New date (optional)
            category: New category (optional)
            notes: New notes (optional)

        Returns:
            Updated transaction or None if not found
        """
        transaction = self.repo.get_by_id(transaction_id)
        if not transaction:
            return None

        # Create updated transaction
        updated_data = transaction.model_dump()
        if description is not None:
            updated_data["description"] = description
        if amount is not None:
            updated_data["amount"] = amount
        if date is not None:
            updated_data["date"] = date
        if category is not None:
            updated_data["category"] = category
        if notes is not None:
            updated_data["notes"] = notes

        updated = Transaction(**updated_data)
        self.repo.update(updated)
        return updated

    def delete_transaction(self, transaction_id: str) -> bool:
        """
        Delete a transaction.

        Args:
            transaction_id: Transaction ID

        Returns:
            True if deleted
        """
        return self.repo.delete(transaction_id)

    def delete_multiple(self, transaction_ids: List[str]) -> int:
        """
        Delete multiple transactions.

        Args:
            transaction_ids: List of transaction IDs

        Returns:
            Number of transactions deleted
        """
        return self.repo.delete_multiple(transaction_ids)

    def split_transaction(
        self, transaction_id: str, splits: List[SplitTransaction]
    ) -> List[Transaction]:
        """
        Split a transaction into multiple transactions.

        Args:
            transaction_id: Original transaction ID
            splits: List of split definitions

        Returns:
            List of new split transactions

        Raises:
            ValueError: If splits don't sum to original amount
        """
        original = self.repo.get_by_id(transaction_id)
        if not original:
            raise ValueError(f"Transaction {transaction_id} not found")

        # Validate split amounts sum to original
        total_split = sum(s.amount for s in splits)
        if abs(total_split - abs(original.amount)) > Decimal("0.01"):
            raise ValueError(
                f"Split amounts ({total_split}) must equal original amount ({abs(original.amount)})"
            )

        # Create split transactions
        split_transactions = []
        for split in splits:
            # Determine amount sign based on original
            amount = (
                -abs(split.amount) if original.amount < 0 else abs(split.amount)
            )

            split_txn = Transaction(
                date=original.date,
                amount=amount,
                description=f"{original.description} - {split.description or split.category.name}",
                category=split.category,
                transaction_type=original.transaction_type,
                account=original.account,
                reference=original.reference,
                notes=split.description,
                id=str(uuid.uuid4()),
                parent_transaction_id=transaction_id,
            )
            split_transactions.append(split_txn)

        # Save split transactions
        self.repo.save(split_transactions)

        # Optionally delete or mark original as split
        # For now, we'll keep the original but could delete it

        return split_transactions

    def merge_transactions(
        self, transaction_ids: List[str], keep_first: bool = True
    ) -> Optional[Transaction]:
        """
        Merge multiple transactions into one.

        Args:
            transaction_ids: List of transaction IDs to merge
            keep_first: If True, keep first transaction's details; otherwise combine

        Returns:
            Merged transaction or None
        """
        if len(transaction_ids) < 2:
            raise ValueError("Need at least 2 transactions to merge")

        transactions = []
        for txn_id in transaction_ids:
            txn = self.repo.get_by_id(txn_id)
            if not txn:
                raise ValueError(f"Transaction {txn_id} not found")
            transactions.append(txn)

        if keep_first:
            # Use first transaction as base
            merged = transactions[0]
            # Sum amounts
            total_amount = sum(t.amount for t in transactions)
            merged = Transaction(
                **merged.model_dump(),
                amount=total_amount,
                description=f"{merged.description} (merged)",
            )
        else:
            # Combine all details
            total_amount = sum(t.amount for t in transactions)
            descriptions = [t.description for t in transactions]
            merged = Transaction(
                date=transactions[0].date,
                amount=total_amount,
                description=", ".join(descriptions),
                category=transactions[0].category,
                transaction_type=transactions[0].transaction_type,
                account=transactions[0].account,
                notes=f"Merged {len(transactions)} transactions",
                id=str(uuid.uuid4()),
            )

        # Save merged transaction
        self.repo.save([merged])

        # Delete original transactions
        self.repo.delete_multiple(transaction_ids)

        return merged

    def bulk_edit(
        self,
        transaction_ids: List[str],
        category: Optional[Category] = None,
        notes: Optional[str] = None,
    ) -> int:
        """
        Bulk edit multiple transactions.

        Args:
            transaction_ids: List of transaction IDs
            category: Category to assign (optional)
            notes: Notes to add (optional)

        Returns:
            Number of transactions updated
        """
        updated_count = 0
        for txn_id in transaction_ids:
            transaction = self.repo.get_by_id(txn_id)
            if not transaction:
                continue

            updated_data = transaction.model_dump()
            if category is not None:
                updated_data["category"] = category
            if notes is not None:
                existing_notes = updated_data.get("notes", "")
                updated_data["notes"] = (
                    f"{existing_notes}\n{notes}" if existing_notes else notes
                )

            updated = Transaction(**updated_data)
            if self.repo.update(updated):
                updated_count += 1

        return updated_count

