"""
Category rules management module.

This module provides UI-friendly management of category mapping rules.
"""

import json
import logging
import re
from pathlib import Path
from typing import Dict, List, Optional, Pattern

from banking.category_mapper import CategoryMapper, CategoryRule
from banking.models import Category, Transaction

logger = logging.getLogger(__name__)


class CategoryRulesManager:
    """Manages category mapping rules with UI support."""

    def __init__(self, data_dir: Path):
        """
        Initialize rules manager.

        Args:
            data_dir: Data directory for storing custom rules
        """
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.custom_rules_file = self.data_dir / "custom_category_rules.json"
        self.mapper = CategoryMapper()
        self._load_custom_rules()

    def _load_custom_rules(self) -> None:
        """Load custom rules from storage."""
        if not self.custom_rules_file.exists():
            return

        try:
            with open(self.custom_rules_file, "r", encoding="utf-8") as f:
                data = json.load(f)

            for rule_data in data.get("rules", []):
                try:
                    pattern = re.compile(rule_data["pattern"])
                    rule = CategoryRule(
                        pattern=pattern,
                        category_name=rule_data["category_name"],
                        parent_category=rule_data.get("parent_category"),
                        case_sensitive=rule_data.get("case_sensitive", False),
                    )
                    self.mapper.rules.append(rule)
                except Exception as e:
                    logger.warning(f"Error loading rule: {e}")

        except Exception as e:
            logger.error(f"Error loading custom rules: {e}")

    def add_rule(
        self,
        pattern: str,
        category_name: str,
        parent_category: Optional[str] = None,
        case_sensitive: bool = False,
        priority: Optional[int] = None,
    ) -> bool:
        """
        Add a custom category rule.

        Args:
            pattern: Regex pattern to match
            category_name: Category name
            parent_category: Optional parent category
            case_sensitive: Whether pattern is case sensitive
            priority: Rule priority (lower = higher priority)

        Returns:
            True if added successfully
        """
        try:
            compiled_pattern = re.compile(pattern) if case_sensitive else re.compile(pattern, re.IGNORECASE)
            rule = CategoryRule(
                pattern=compiled_pattern,
                category_name=category_name,
                parent_category=parent_category,
                case_sensitive=case_sensitive,
            )

            if priority is not None and 0 <= priority < len(self.mapper.rules):
                self.mapper.rules.insert(priority, rule)
            else:
                self.mapper.rules.append(rule)

            self._save_custom_rules()
            return True
        except re.error as e:
            logger.error(f"Invalid regex pattern: {e}")
            return False

    def remove_rule(self, pattern: str, category_name: str) -> bool:
        """
        Remove a custom rule.

        Args:
            pattern: Rule pattern
            category_name: Category name

        Returns:
            True if removed
        """
        original_count = len(self.mapper.rules)
        self.mapper.rules = [
            r
            for r in self.mapper.rules
            if not (r.pattern.pattern == pattern and r.category_name == category_name)
        ]

        if len(self.mapper.rules) < original_count:
            self._save_custom_rules()
            return True
        return False

    def get_all_rules(self) -> List[Dict]:
        """
        Get all rules (default + custom).

        Returns:
            List of rule dictionaries
        """
        rules = []
        for rule in self.mapper.rules:
            rules.append(
                {
                    "pattern": rule.pattern.pattern,
                    "category_name": rule.category_name,
                    "parent_category": rule.parent_category,
                    "case_sensitive": rule.case_sensitive,
                }
            )
        return rules

    def test_rule(self, pattern: str, test_strings: List[str]) -> Dict:
        """
        Test a rule pattern against test strings.

        Args:
            pattern: Regex pattern to test
            test_strings: List of strings to test against

        Returns:
            Dictionary with test results
        """
        try:
            compiled = re.compile(pattern, re.IGNORECASE)
            results = []
            for test_str in test_strings:
                match = compiled.search(test_str)
                results.append(
                    {
                        "string": test_str,
                        "matches": match is not None,
                        "matched_text": match.group() if match else None,
                    }
                )

            return {"valid": True, "results": results}
        except re.error as e:
            return {"valid": False, "error": str(e), "results": []}

    def test_against_transactions(
        self, pattern: str, transactions: List[Transaction], limit: int = 10
    ) -> List[Dict]:
        """
        Test rule against existing transactions.

        Args:
            pattern: Regex pattern
            transactions: List of transactions
            limit: Maximum number of results

        Returns:
            List of matching transaction info
        """
        try:
            compiled = re.compile(pattern, re.IGNORECASE)
            matches = []

            for transaction in transactions:
                if compiled.search(transaction.description):
                    matches.append(
                        {
                            "date": transaction.date.isoformat(),
                            "description": transaction.description,
                            "amount": str(transaction.amount),
                            "current_category": (
                                transaction.category.name if transaction.category else None
                            ),
                        }
                    )
                    if len(matches) >= limit:
                        break

            return matches
        except re.error:
            return []

    def _save_custom_rules(self) -> None:
        """Save custom rules to file."""
        # Only save rules that aren't in default mapper
        # For simplicity, save all rules (can be refined later)
        custom_rules = []
        for rule in self.mapper.rules:
            custom_rules.append(
                {
                    "pattern": rule.pattern.pattern,
                    "category_name": rule.category_name,
                    "parent_category": rule.parent_category,
                    "case_sensitive": rule.case_sensitive,
                }
            )

        data = {"rules": custom_rules}
        with open(self.custom_rules_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

    def export_rules(self, output_file: Path) -> bool:
        """
        Export rules to file.

        Args:
            output_file: Output file path

        Returns:
            True if successful
        """
        try:
            rules = self.get_all_rules()
            data = {"rules": rules}
            with open(output_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
            return True
        except Exception as e:
            logger.error(f"Error exporting rules: {e}")
            return False

    def import_rules(self, input_file: Path) -> bool:
        """
        Import rules from file.

        Args:
            input_file: Input file path

        Returns:
            True if successful
        """
        try:
            with open(input_file, "r", encoding="utf-8") as f:
                data = json.load(f)

            for rule_data in data.get("rules", []):
                self.add_rule(
                    pattern=rule_data["pattern"],
                    category_name=rule_data["category_name"],
                    parent_category=rule_data.get("parent_category"),
                    case_sensitive=rule_data.get("case_sensitive", False),
                )

            return True
        except Exception as e:
            logger.error(f"Error importing rules: {e}")
            return False

