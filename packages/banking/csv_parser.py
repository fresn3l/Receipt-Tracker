"""
CSV parser for bank statement files.

This module provides functionality to parse bank statement CSV files in multiple formats.
It automatically detects the CSV format and converts rows into Transaction objects.

Supported Formats:
    1. Standard Format: Date, Description, Amount, Balance
    2. Alternative Format: Transaction Date, Post Date, Description, Category, Type, Amount
    3. Debit/Credit Format: Date, Description, Debit, Credit, Balance

The parser handles:
- Automatic format detection
- Flexible date parsing (ISO, US, European formats)
- Amount parsing with currency symbols and commas
- Error handling with row-level reporting

Example:
    >>> from banking.csv_parser import parse_csv
    >>> from pathlib import Path
    >>> 
    >>> transactions = parse_csv(Path("bank_statement.csv"))
    >>> print(f"Parsed {len(transactions)} transactions")
    
    >>> from banking.csv_parser import CSVParser
    >>> parser = CSVParser(account="CHECKING-123")
    >>> format_type = parser.detect_format(Path("statement.csv"))
    >>> transactions = parser.parse(Path("statement.csv"))
"""

import csv
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from enum import Enum
from pathlib import Path
from typing import List, Optional

from banking.models import Category, Transaction, TransactionType


class CSVFormat(str, Enum):
    """Supported CSV formats."""

    STANDARD = "standard"  # Date, Description, Amount, Balance
    ALTERNATIVE = "alternative"  # Transaction Date, Post Date, Description, Category, Type, Amount
    DEBIT_CREDIT = "debit_credit"  # Date, Description, Debit, Credit, Balance
    UNKNOWN = "unknown"


class CSVParserError(Exception):
    """Base exception for CSV parser errors."""

    pass


class UnsupportedFormatError(CSVParserError):
    """Raised when CSV format is not supported."""

    pass


class InvalidDataError(CSVParserError):
    """Raised when CSV data is invalid or malformed."""

    pass


class CSVParser:
    """Parser for bank statement CSV files."""

    def __init__(self, account: Optional[str] = None):
        """
        Initialize CSV parser.

        Args:
            account: Optional account identifier to assign to all transactions
        """
        self.account = account

    def detect_format(self, file_path: Path) -> CSVFormat:
        """
        Detect the format of a CSV file by examining headers.

        Args:
            file_path: Path to CSV file

        Returns:
            Detected CSV format

        Raises:
            CSVParserError: If file cannot be read
        """
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                headers = reader.fieldnames
                if headers is None:
                    raise InvalidDataError("CSV file has no headers")

                headers_lower = [h.lower().strip() for h in headers]

                # Check for alternative format
                if "transaction date" in headers_lower and "type" in headers_lower:
                    return CSVFormat.ALTERNATIVE

                # Check for debit/credit format
                if "debit" in headers_lower and "credit" in headers_lower:
                    return CSVFormat.DEBIT_CREDIT

                # Check for standard format
                if "date" in headers_lower and "amount" in headers_lower and "description" in headers_lower:
                    return CSVFormat.STANDARD

                return CSVFormat.UNKNOWN

        except FileNotFoundError:
            raise CSVParserError(f"File not found: {file_path}")
        except Exception as e:
            raise CSVParserError(f"Error reading CSV file: {e}") from e

    def parse(self, file_path: Path) -> List[Transaction]:
        """
        Parse a CSV file and return list of transactions.

        Args:
            file_path: Path to CSV file

        Returns:
            List of Transaction objects

        Raises:
            UnsupportedFormatError: If CSV format is not supported
            InvalidDataError: If CSV data is invalid
            CSVParserError: For other parsing errors
        """
        format_type = self.detect_format(file_path)

        if format_type == CSVFormat.UNKNOWN:
            raise UnsupportedFormatError(f"Unsupported CSV format in file: {file_path}")

        parser_map = {
            CSVFormat.STANDARD: self._parse_standard,
            CSVFormat.ALTERNATIVE: self._parse_alternative,
            CSVFormat.DEBIT_CREDIT: self._parse_debit_credit,
        }

        parser = parser_map[format_type]
        return parser(file_path)

    def _parse_standard(self, file_path: Path) -> List[Transaction]:
        """Parse standard format CSV (Date, Description, Amount, Balance)."""
        transactions = []

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row_num, row in enumerate(reader, start=2):  # Start at 2 (header is row 1)
                    try:
                        # Parse date
                        date_str = row.get("Date", "").strip()
                        if not date_str:
                            continue  # Skip empty rows
                        transaction_date = self._parse_date(date_str)

                        # Parse description
                        description = row.get("Description", "").strip()
                        if not description:
                            raise InvalidDataError(f"Row {row_num}: Missing description")

                        # Parse amount
                        amount_str = row.get("Amount", "").strip()
                        amount = self._parse_decimal(amount_str)
                        if amount == 0:
                            continue  # Skip zero-amount transactions

                        # Determine transaction type
                        transaction_type = TransactionType.CREDIT if amount > 0 else TransactionType.DEBIT

                        # Parse balance if available
                        balance = None
                        balance_str = row.get("Balance", "").strip()
                        if balance_str:
                            balance = self._parse_decimal(balance_str)

                        transaction = Transaction(
                            date=transaction_date,
                            amount=amount,
                            description=description,
                            transaction_type=transaction_type,
                            account=self.account,
                            balance=balance,
                        )
                        transactions.append(transaction)

                    except (ValueError, InvalidDataError) as e:
                        raise InvalidDataError(f"Row {row_num}: {e}") from e

        except Exception as e:
            if isinstance(e, InvalidDataError):
                raise
            raise CSVParserError(f"Error parsing standard format CSV: {e}") from e

        return transactions

    def _parse_alternative(self, file_path: Path) -> List[Transaction]:
        """Parse alternative format CSV (Transaction Date, Post Date, Description, Category, Type, Amount)."""
        transactions = []

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row_num, row in enumerate(reader, start=2):
                    try:
                        # Parse date (prefer Transaction Date, fallback to Post Date)
                        date_str = row.get("Transaction Date", "").strip() or row.get("Post Date", "").strip()
                        if not date_str:
                            continue
                        transaction_date = self._parse_date(date_str)

                        # Parse description
                        description = row.get("Description", "").strip()
                        if not description:
                            raise InvalidDataError(f"Row {row_num}: Missing description")

                        # Parse amount
                        amount_str = row.get("Amount", "").strip()
                        amount = self._parse_decimal(amount_str)
                        if amount == 0:
                            continue

                        # Parse transaction type
                        type_str = row.get("Type", "").strip().lower()
                        if type_str == "credit":
                            transaction_type = TransactionType.CREDIT
                        elif type_str == "debit":
                            transaction_type = TransactionType.DEBIT
                        elif type_str == "transfer":
                            transaction_type = TransactionType.TRANSFER
                        else:
                            # Infer from amount
                            transaction_type = TransactionType.CREDIT if amount > 0 else TransactionType.DEBIT

                        # Parse category if available
                        category = None
                        category_str = row.get("Category", "").strip()
                        if category_str:
                            category = Category(name=category_str)

                        transaction = Transaction(
                            date=transaction_date,
                            amount=amount,
                            description=description,
                            transaction_type=transaction_type,
                            category=category,
                            account=self.account,
                        )
                        transactions.append(transaction)

                    except (ValueError, InvalidDataError) as e:
                        raise InvalidDataError(f"Row {row_num}: {e}") from e

        except Exception as e:
            if isinstance(e, InvalidDataError):
                raise
            raise CSVParserError(f"Error parsing alternative format CSV: {e}") from e

        return transactions

    def _parse_debit_credit(self, file_path: Path) -> List[Transaction]:
        """Parse debit/credit format CSV (Date, Description, Debit, Credit, Balance)."""
        transactions = []

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row_num, row in enumerate(reader, start=2):
                    try:
                        # Parse date
                        date_str = row.get("Date", "").strip()
                        if not date_str:
                            continue
                        transaction_date = self._parse_date(date_str)

                        # Parse description
                        description = row.get("Description", "").strip()
                        if not description:
                            raise InvalidDataError(f"Row {row_num}: Missing description")

                        # Parse debit and credit
                        debit_str = row.get("Debit", "").strip()
                        credit_str = row.get("Credit", "").strip()

                        debit = self._parse_decimal(debit_str) if debit_str else Decimal("0")
                        credit = self._parse_decimal(credit_str) if credit_str else Decimal("0")

                        # Determine amount and type
                        if debit > 0 and credit > 0:
                            raise InvalidDataError(f"Row {row_num}: Both debit and credit cannot be non-zero")
                        elif debit > 0:
                            amount = -debit  # Negative for debits
                            transaction_type = TransactionType.DEBIT
                        elif credit > 0:
                            amount = credit  # Positive for credits
                            transaction_type = TransactionType.CREDIT
                        else:
                            continue  # Skip rows with no amount

                        # Parse balance if available
                        balance = None
                        balance_str = row.get("Balance", "").strip()
                        if balance_str:
                            balance = self._parse_decimal(balance_str)

                        transaction = Transaction(
                            date=transaction_date,
                            amount=amount,
                            description=description,
                            transaction_type=transaction_type,
                            account=self.account,
                            balance=balance,
                        )
                        transactions.append(transaction)

                    except (ValueError, InvalidDataError) as e:
                        raise InvalidDataError(f"Row {row_num}: {e}") from e

        except Exception as e:
            if isinstance(e, InvalidDataError):
                raise
            raise CSVParserError(f"Error parsing debit/credit format CSV: {e}") from e

        return transactions

    @staticmethod
    def _parse_date(date_str: str) -> date:
        """
        Parse date string into date object.

        Supports multiple date formats commonly used in bank statements:
        - ISO format: YYYY-MM-DD (e.g., "2024-01-15")
        - US format: MM/DD/YYYY (e.g., "01/15/2024")
        - European format: DD/MM/YYYY (e.g., "15/01/2024")

        The method tries formats in order until one succeeds.

        Args:
            date_str: Date string to parse

        Returns:
            Parsed date object

        Raises:
            ValueError: If date cannot be parsed in any supported format

        Example:
            >>> CSVParser._parse_date("2024-01-15")
            datetime.date(2024, 1, 15)
            >>> CSVParser._parse_date("01/15/2024")
            datetime.date(2024, 1, 15)
        """
        date_str = date_str.strip()

        # Try ISO format first (YYYY-MM-DD) - most common in modern exports
        try:
            return datetime.strptime(date_str, "%Y-%m-%d").date()
        except ValueError:
            pass

        # Try US format (MM/DD/YYYY) - common in US bank statements
        try:
            return datetime.strptime(date_str, "%m/%d/%Y").date()
        except ValueError:
            pass

        # Try European format (DD/MM/YYYY) - common in European bank statements
        try:
            return datetime.strptime(date_str, "%d/%m/%Y").date()
        except ValueError:
            pass

        # If all formats fail, raise an error with helpful message
        raise ValueError(f"Unable to parse date: {date_str}. Supported formats: YYYY-MM-DD, MM/DD/YYYY, DD/MM/YYYY")

    @staticmethod
    def _parse_decimal(value_str: str) -> Decimal:
        """
        Parse decimal string into Decimal object.

        Handles various formatting commonly found in bank statements:
        - Currency symbols: $, €, £
        - Thousands separators: commas (1,234.56)
        - Whitespace
        - Negative signs: - or parentheses

        Uses Decimal for precise monetary calculations (avoids floating-point errors).

        Args:
            value_str: Decimal string to parse (e.g., "$1,234.56", "-50.00")

        Returns:
            Parsed Decimal object

        Raises:
            ValueError: If value cannot be parsed

        Example:
            >>> CSVParser._parse_decimal("$1,234.56")
            Decimal('1234.56')
            >>> CSVParser._parse_decimal("-50.00")
            Decimal('-50.00')
            >>> CSVParser._parse_decimal("")
            Decimal('0')
        """
        if not value_str or not value_str.strip():
            return Decimal("0")

        # Remove common formatting characters
        # Order matters: remove $ before processing negative signs
        cleaned = value_str.strip().replace("$", "").replace(",", "").replace(" ", "")

        try:
            return Decimal(cleaned)
        except InvalidOperation as e:
            raise ValueError(f"Unable to parse decimal: {value_str}") from e


def parse_csv(file_path: Path, account: Optional[str] = None) -> List[Transaction]:
    """
    Convenience function to parse a CSV file.

    Args:
        file_path: Path to CSV file
        account: Optional account identifier

    Returns:
        List of Transaction objects
    """
    parser = CSVParser(account=account)
    return parser.parse(file_path)

