"""
CSV parser for bank statement files.

Supports multiple formats with automatic detection:
  1. Standard: Date, Description, Amount, Balance (signed amounts)
  2. Alternative: Transaction Date, Type, Amount
  3. Debit/Credit columns: Date, Description, Debit, Credit, Balance
  4. Indicator: Credit Debit Indicator + absolute Amount (common bank exports)
"""

from __future__ import annotations

import csv
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from enum import Enum
from pathlib import Path
from typing import Dict, Iterable, List, Optional

from banking.models import Category, Transaction, TransactionType


class CSVFormat(str, Enum):
    """Supported CSV formats."""

    STANDARD = "standard"
    ALTERNATIVE = "alternative"
    DEBIT_CREDIT = "debit_credit"
    INDICATOR = "indicator"  # Absolute amounts + Credit Debit Indicator
    UNKNOWN = "unknown"


class CSVParserError(Exception):
    """Base exception for CSV parser errors."""


class UnsupportedFormatError(CSVParserError):
    """Raised when CSV format is not supported."""


class InvalidDataError(CSVParserError):
    """Raised when CSV data is invalid or malformed."""


def _normalize_header(name: str) -> str:
    return name.replace("\ufeff", "").strip().lower()


def _header_map(fieldnames: Optional[Iterable[str]]) -> Dict[str, str]:
    """Map normalized header -> original header key."""
    mapping: Dict[str, str] = {}
    if not fieldnames:
        return mapping
    for raw in fieldnames:
        mapping[_normalize_header(raw)] = raw
    return mapping


def _cell(row: dict, headers: Dict[str, str], *candidates: str) -> str:
    """Read a cell by trying several header names (case-insensitive)."""
    for candidate in candidates:
        key = headers.get(_normalize_header(candidate))
        if key is not None:
            value = row.get(key)
            if value is not None and str(value).strip() != "":
                return str(value).strip()
    return ""


def _classify_indicator(value: str) -> Optional[TransactionType]:
    """Map Credit Debit Indicator / Type strings to TransactionType."""
    text = value.strip().lower()
    if not text:
        return None
    if text in {"credit", "cr", "c"} or "credit" in text:
        return TransactionType.CREDIT
    if text in {"debit", "dr", "d"} or "debit" in text or text in {"pos", "purchase", "sale", "withdrawal"}:
        return TransactionType.DEBIT
    if "transfer" in text:
        return TransactionType.TRANSFER
    return None


class CSVParser:
    """Parser for bank statement CSV files."""

    def __init__(self, account: Optional[str] = None):
        self.account = account

    def detect_format(self, file_path: Path) -> CSVFormat:
        try:
            with open(file_path, "r", encoding="utf-8-sig") as f:
                reader = csv.DictReader(f)
                headers = _header_map(reader.fieldnames)
                if not headers:
                    raise InvalidDataError("CSV file has no headers")

                if "credit debit indicator" in headers and "amount" in headers:
                    return CSVFormat.INDICATOR

                if "debit" in headers and "credit" in headers:
                    return CSVFormat.DEBIT_CREDIT

                if "transaction date" in headers and ("type" in headers or "amount" in headers):
                    return CSVFormat.ALTERNATIVE

                if "date" in headers and "amount" in headers and "description" in headers:
                    return CSVFormat.STANDARD

                return CSVFormat.UNKNOWN

        except FileNotFoundError:
            raise CSVParserError(f"File not found: {file_path}")
        except Exception as e:
            if isinstance(e, InvalidDataError):
                raise
            raise CSVParserError(f"Error reading CSV file: {e}") from e

    def parse(self, file_path: Path) -> List[Transaction]:
        format_type = self.detect_format(file_path)
        if format_type == CSVFormat.UNKNOWN:
            raise UnsupportedFormatError(f"Unsupported CSV format in file: {file_path}")

        parser_map = {
            CSVFormat.STANDARD: self._parse_standard,
            CSVFormat.ALTERNATIVE: self._parse_alternative,
            CSVFormat.DEBIT_CREDIT: self._parse_debit_credit,
            CSVFormat.INDICATOR: self._parse_indicator,
        }
        return parser_map[format_type](file_path)

    def _iter_rows(self, file_path: Path):
        with open(file_path, "r", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            headers = _header_map(reader.fieldnames)
            for row_num, row in enumerate(reader, start=2):
                yield row_num, row, headers

    def _parse_indicator(self, file_path: Path) -> List[Transaction]:
        """Parse absolute-amount exports that include Credit Debit Indicator."""
        transactions: List[Transaction] = []

        try:
            for row_num, row, headers in self._iter_rows(file_path):
                try:
                    date_str = _cell(
                        row,
                        headers,
                        "Transaction Date",
                        "Posting Date",
                        "Date",
                    )
                    if not date_str:
                        continue
                    transaction_date = self._parse_date(date_str)

                    description = _cell(row, headers, "Description", "Memo", "Payee")
                    if not description:
                        raise InvalidDataError(f"Row {row_num}: Missing description")

                    amount = abs(self._parse_decimal(_cell(row, headers, "Amount")))
                    if amount == 0:
                        continue

                    indicator = _cell(
                        row,
                        headers,
                        "Credit Debit Indicator",
                        "Debit/Credit",
                        "Credit/Debit",
                    )
                    type_hint = _cell(row, headers, "type", "Type", "Type Group")
                    transaction_type = _classify_indicator(indicator) or _classify_indicator(type_hint)
                    if transaction_type is None:
                        raise InvalidDataError(
                            f"Row {row_num}: Missing Credit Debit Indicator (cannot classify amount)"
                        )

                    # Store signed amount: expenses negative, income positive
                    if transaction_type == TransactionType.CREDIT:
                        signed_amount = amount
                    else:
                        # DEBIT and TRANSFER-out use negative amounts
                        signed_amount = -amount
                        if transaction_type == TransactionType.TRANSFER:
                            transaction_type = TransactionType.DEBIT

                    category = None
                    category_str = _cell(row, headers, "Category")
                    if category_str:
                        category = Category(name=category_str)

                    reference = _cell(row, headers, "Reference", "Check Serial Number") or None

                    transactions.append(
                        Transaction(
                            date=transaction_date,
                            amount=signed_amount,
                            description=description,
                            transaction_type=transaction_type,
                            category=category,
                            account=self.account,
                            reference=reference,
                        )
                    )
                except (ValueError, InvalidDataError) as e:
                    raise InvalidDataError(f"Row {row_num}: {e}") from e
        except Exception as e:
            if isinstance(e, (InvalidDataError, CSVParserError)):
                raise
            raise CSVParserError(f"Error parsing indicator format CSV: {e}") from e

        return transactions

    def _parse_standard(self, file_path: Path) -> List[Transaction]:
        transactions: List[Transaction] = []
        try:
            for row_num, row, headers in self._iter_rows(file_path):
                try:
                    date_str = _cell(row, headers, "Date")
                    if not date_str:
                        continue
                    transaction_date = self._parse_date(date_str)

                    description = _cell(row, headers, "Description")
                    if not description:
                        raise InvalidDataError(f"Row {row_num}: Missing description")

                    amount = self._parse_decimal(_cell(row, headers, "Amount"))
                    if amount == 0:
                        continue

                    transaction_type = (
                        TransactionType.CREDIT if amount > 0 else TransactionType.DEBIT
                    )

                    balance = None
                    balance_str = _cell(row, headers, "Balance")
                    if balance_str:
                        balance = self._parse_decimal(balance_str)

                    transactions.append(
                        Transaction(
                            date=transaction_date,
                            amount=amount,
                            description=description,
                            transaction_type=transaction_type,
                            account=self.account,
                            balance=balance,
                        )
                    )
                except (ValueError, InvalidDataError) as e:
                    raise InvalidDataError(f"Row {row_num}: {e}") from e
        except Exception as e:
            if isinstance(e, InvalidDataError):
                raise
            raise CSVParserError(f"Error parsing standard format CSV: {e}") from e
        return transactions

    def _parse_alternative(self, file_path: Path) -> List[Transaction]:
        transactions: List[Transaction] = []
        try:
            for row_num, row, headers in self._iter_rows(file_path):
                try:
                    date_str = _cell(row, headers, "Transaction Date", "Post Date", "Date")
                    if not date_str:
                        continue
                    transaction_date = self._parse_date(date_str)

                    description = _cell(row, headers, "Description")
                    if not description:
                        raise InvalidDataError(f"Row {row_num}: Missing description")

                    amount = self._parse_decimal(_cell(row, headers, "Amount"))
                    if amount == 0:
                        continue

                    type_str = _cell(row, headers, "Type", "type", "Credit Debit Indicator")
                    transaction_type = _classify_indicator(type_str)
                    if transaction_type is None:
                        transaction_type = (
                            TransactionType.CREDIT if amount > 0 else TransactionType.DEBIT
                        )
                    elif amount > 0 and transaction_type == TransactionType.DEBIT:
                        amount = -amount
                    elif amount < 0 and transaction_type == TransactionType.CREDIT:
                        amount = abs(amount)

                    category = None
                    category_str = _cell(row, headers, "Category")
                    if category_str:
                        category = Category(name=category_str)

                    transactions.append(
                        Transaction(
                            date=transaction_date,
                            amount=amount,
                            description=description,
                            transaction_type=transaction_type,
                            category=category,
                            account=self.account,
                        )
                    )
                except (ValueError, InvalidDataError) as e:
                    raise InvalidDataError(f"Row {row_num}: {e}") from e
        except Exception as e:
            if isinstance(e, InvalidDataError):
                raise
            raise CSVParserError(f"Error parsing alternative format CSV: {e}") from e
        return transactions

    def _parse_debit_credit(self, file_path: Path) -> List[Transaction]:
        transactions: List[Transaction] = []
        try:
            for row_num, row, headers in self._iter_rows(file_path):
                try:
                    date_str = _cell(row, headers, "Date")
                    if not date_str:
                        continue
                    transaction_date = self._parse_date(date_str)

                    description = _cell(row, headers, "Description")
                    if not description:
                        raise InvalidDataError(f"Row {row_num}: Missing description")

                    debit_str = _cell(row, headers, "Debit")
                    credit_str = _cell(row, headers, "Credit")
                    debit = self._parse_decimal(debit_str) if debit_str else Decimal("0")
                    credit = self._parse_decimal(credit_str) if credit_str else Decimal("0")

                    if debit > 0 and credit > 0:
                        raise InvalidDataError(
                            f"Row {row_num}: Both debit and credit cannot be non-zero"
                        )
                    if debit > 0:
                        amount = -debit
                        transaction_type = TransactionType.DEBIT
                    elif credit > 0:
                        amount = credit
                        transaction_type = TransactionType.CREDIT
                    else:
                        continue

                    balance = None
                    balance_str = _cell(row, headers, "Balance")
                    if balance_str:
                        balance = self._parse_decimal(balance_str)

                    transactions.append(
                        Transaction(
                            date=transaction_date,
                            amount=amount,
                            description=description,
                            transaction_type=transaction_type,
                            account=self.account,
                            balance=balance,
                        )
                    )
                except (ValueError, InvalidDataError) as e:
                    raise InvalidDataError(f"Row {row_num}: {e}") from e
        except Exception as e:
            if isinstance(e, InvalidDataError):
                raise
            raise CSVParserError(f"Error parsing debit/credit format CSV: {e}") from e
        return transactions

    @staticmethod
    def _parse_date(date_str: str) -> date:
        date_str = date_str.strip()
        for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%d/%m/%Y", "%m/%d/%y", "%d/%m/%y"):
            try:
                return datetime.strptime(date_str, fmt).date()
            except ValueError:
                continue
        raise ValueError(
            f"Unable to parse date: {date_str}. Supported formats: YYYY-MM-DD, MM/DD/YYYY, DD/MM/YYYY"
        )

    @staticmethod
    def _parse_decimal(value_str: str) -> Decimal:
        if not value_str or not value_str.strip():
            return Decimal("0")
        cleaned = value_str.strip().replace("$", "").replace(",", "").replace(" ", "")
        # Accounting negatives: (123.45)
        if cleaned.startswith("(") and cleaned.endswith(")"):
            cleaned = "-" + cleaned[1:-1]
        try:
            return Decimal(cleaned)
        except InvalidOperation as e:
            raise ValueError(f"Unable to parse decimal: {value_str}") from e


def parse_csv(file_path: Path, account: Optional[str] = None) -> List[Transaction]:
    parser = CSVParser(account=account)
    return parser.parse(file_path)
