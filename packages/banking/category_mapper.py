"""
Category mapping system for automatic transaction categorization.

This module provides pattern-based categorization of transactions using regex rules.
It includes 50+ default rules covering common spending categories and supports
custom rules for user-specific needs.

Categories are organized hierarchically (e.g., "Groceries" under "Food & Dining").
Rules use regex patterns for flexible matching of transaction descriptions.

Default Categories Include:
    - Food & Dining: Groceries, Restaurants, Coffee Shops, Fast Food
    - Transportation: Gas & Fuel, Rideshare, Parking, Public Transit
    - Shopping: General Shopping, Clothing, Pharmacy
    - Bills & Utilities: Electric, Water, Internet, Phone, Cable/TV
    - Entertainment: Streaming Services, Movies, Events, Gaming
    - Health & Fitness: Medical, Dental, Fitness, Pharmacy
    - Income: Salary, Other Income, Refunds
    - And more...

Example:
    >>> from banking.category_mapper import CategoryMapper
    >>> 
    >>> mapper = CategoryMapper()
    >>> category = mapper.categorize("GROCERY STORE #1234")
    >>> print(category.name)  # "Groceries"
    >>> print(category.parent)  # "Food & Dining"
    
    >>> # Add custom rule
    >>> mapper.add_custom_rule(
    ...     r"(?i)\\b(custom.?merchant)\\b",
    ...     "Custom Category",
    ...     "Custom Parent"
    ... )
"""

import re
from dataclasses import dataclass
from typing import Dict, List, Optional, Pattern

from banking.models import Category


@dataclass
class CategoryRule:
    """Rule for matching transactions to categories."""

    pattern: Pattern[str]
    category_name: str
    parent_category: Optional[str] = None
    case_sensitive: bool = False


class CategoryMapper:
    """Maps transaction descriptions to categories using keyword and pattern matching."""

    def __init__(self, custom_rules: Optional[List[CategoryRule]] = None):
        """
        Initialize category mapper.

        Args:
            custom_rules: Optional list of custom rules to add to default rules
        """
        self.rules: List[CategoryRule] = []
        self._load_default_rules()
        if custom_rules:
            self.rules.extend(custom_rules)

    def _load_default_rules(self) -> None:
        """Load default category mapping rules."""
        # Food & Dining
        self._add_rule(r"(?i)\b(grocery|supermarket|whole foods|trader joe|kroger|safeway|publix|wegmans|aldi|food lion|stop.?shop)\b", "Groceries", "Food & Dining")
        self._add_rule(r"(?i)\b(restaurant|cafe|diner|bistro|steakhouse|pizzeria|pizza|mcdonald|burger|kfc|taco|chipotle|subway|domino)\b", "Restaurants", "Food & Dining")
        self._add_rule(r"(?i)\b(starbucks|coffee|espresso|cappuccino|latte|dunkin|peet.?s|tim.?hortons)\b", "Coffee Shops", "Food & Dining")
        self._add_rule(r"(?i)\b(fast.?food|drive.?thru|takeout|delivery)\b", "Fast Food", "Food & Dining")

        # Transportation
        self._add_rule(r"(?i)\b(gas|petrol|fuel|shell|exxon|bp|chevron|mobil|arco|76|valero|sunoco|citgo)\b", "Gas & Fuel", "Transportation")
        self._add_rule(r"(?i)\b(uber|lyft|taxi|cab|ride.?share|rideshare)\b", "Rideshare", "Transportation")
        self._add_rule(r"(?i)\b(parking|parking.?meter|garage|valet)\b", "Parking", "Transportation")
        self._add_rule(r"(?i)\b(metro|subway|bus|transit|public.?transport|train|amtrak)\b", "Public Transit", "Transportation")
        self._add_rule(r"(?i)\b(car.?wash|auto.?wash|detailing)\b", "Car Maintenance", "Transportation")

        # Shopping
        self._add_rule(r"(?i)\b(amazon|target|walmart|costco|sam.?club|best.?buy|home.?depot|lowes)\b", "General Shopping", "Shopping")
        self._add_rule(r"(?i)\b(clothing|apparel|nike|adidas|zara|h.?m|forever.?21|macy.?s|nordstrom)\b", "Clothing", "Shopping")
        self._add_rule(r"(?i)\b(pharmacy|drugstore|cvs|walgreens|rite.?aid|pharmacy)\b", "Pharmacy", "Shopping")

        # Bills & Utilities
        self._add_rule(r"(?i)\b(electric|power|energy|utility|electricity)\b", "Electric", "Bills & Utilities")
        self._add_rule(r"(?i)\b(water|sewer|waterworks)\b", "Water", "Bills & Utilities")
        self._add_rule(r"(?i)\b(gas.?bill|natural.?gas)\b", "Gas Utility", "Bills & Utilities")
        self._add_rule(r"(?i)\b(internet|isp|comcast|verizon|att|xfinity|spectrum)\b", "Internet", "Bills & Utilities")
        self._add_rule(r"(?i)\b(phone|mobile|cellular|verizon|att|t.?mobile|sprint)\b", "Phone", "Bills & Utilities")
        self._add_rule(r"(?i)\b(cable|tv|television|directv|dish)\b", "Cable/TV", "Bills & Utilities")

        # Entertainment
        self._add_rule(r"(?i)\b(netflix|hulu|disney.?plus|prime|spotify|apple.?music|youtube.?premium)\b", "Streaming Services", "Entertainment")
        self._add_rule(r"(?i)\b(movie|cinema|theater|amc|regal|fandango)\b", "Movies", "Entertainment")
        self._add_rule(r"(?i)\b(concert|ticketmaster|stubhub|event)\b", "Events", "Entertainment")
        self._add_rule(r"(?i)\b(game|gaming|steam|playstation|xbox|nintendo)\b", "Gaming", "Entertainment")

        # Health & Fitness
        self._add_rule(r"(?i)\b(doctor|physician|medical|clinic|hospital|urgent.?care)\b", "Medical", "Health & Fitness")
        self._add_rule(r"(?i)\b(dentist|dental|orthodontist)\b", "Dental", "Health & Fitness")
        self._add_rule(r"(?i)\b(gym|fitness|yoga|pilates|personal.?trainer)\b", "Fitness", "Health & Fitness")
        self._add_rule(r"(?i)\b(pharmacy|prescription|medication)\b", "Pharmacy", "Health & Fitness")

        # Income
        self._add_rule(r"(?i)\b(salary|payroll|paycheck|wages|income|direct.?deposit)\b", "Salary", "Income")
        self._add_rule(r"(?i)\b(bonus|commission|freelance|contract)\b", "Other Income", "Income")
        self._add_rule(r"(?i)\b(refund|reimbursement|rebate)\b", "Refunds", "Income")

        # Transfers
        self._add_rule(r"(?i)\b(transfer|savings|investment|401k|ira)\b", "Transfers", "Transfers")

        # Subscriptions
        self._add_rule(r"(?i)\b(subscription|recurring|monthly.?fee|annual.?fee)\b", "Subscriptions", "Subscriptions")

        # Education
        self._add_rule(r"(?i)\b(tuition|school|university|college|education|student.?loan)\b", "Education", "Education")

        # Insurance
        self._add_rule(r"(?i)\b(insurance|premium|geico|state.?farm|allstate|progressive)\b", "Insurance", "Insurance")

        # Banking
        self._add_rule(r"(?i)\b(fee|atm|overdraft|service.?charge|bank.?fee)\b", "Banking Fees", "Banking")

    def _add_rule(self, pattern: str, category_name: str, parent_category: Optional[str] = None) -> None:
        """
        Add a category rule.

        Args:
            pattern: Regex pattern to match transaction descriptions
            category_name: Name of the category
            parent_category: Optional parent category name
        """
        compiled_pattern = re.compile(pattern)
        rule = CategoryRule(
            pattern=compiled_pattern, category_name=category_name, parent_category=parent_category
        )
        self.rules.append(rule)

    def categorize(self, description: str) -> Optional[Category]:
        """
        Categorize a transaction based on its description.

        Args:
            description: Transaction description/merchant name

        Returns:
            Category object if match found, None otherwise
        """
        description_clean = description.strip()

        # Check rules in order (first match wins)
        for rule in self.rules:
            if rule.pattern.search(description_clean):
                return Category(
                    name=rule.category_name, parent=rule.parent_category, description=None
                )

        return None

    def add_custom_rule(
        self, pattern: str, category_name: str, parent_category: Optional[str] = None, case_sensitive: bool = False
    ) -> None:
        """
        Add a custom categorization rule.

        Args:
            pattern: Regex pattern to match transaction descriptions
            category_name: Name of the category
            parent_category: Optional parent category name
            case_sensitive: Whether pattern matching is case sensitive
        """
        flags = 0 if case_sensitive else re.IGNORECASE
        compiled_pattern = re.compile(pattern, flags)
        rule = CategoryRule(
            pattern=compiled_pattern,
            category_name=category_name,
            parent_category=parent_category,
            case_sensitive=case_sensitive,
        )
        self.rules.append(rule)

    def get_all_categories(self) -> Dict[str, List[str]]:
        """
        Get all categories organized by parent.

        Returns:
            Dictionary mapping parent categories to list of child categories
        """
        categories: Dict[str, List[str]] = {}
        seen = set()

        for rule in self.rules:
            if rule.parent_category:
                if rule.parent_category not in categories:
                    categories[rule.parent_category] = []
                if rule.category_name not in seen:
                    categories[rule.parent_category].append(rule.category_name)
                    seen.add(rule.category_name)
            else:
                if "Other" not in categories:
                    categories["Other"] = []
                if rule.category_name not in seen:
                    categories["Other"].append(rule.category_name)
                    seen.add(rule.category_name)

        return categories


def get_default_mapper() -> CategoryMapper:
    """
    Get a CategoryMapper instance with default rules.

    Returns:
        CategoryMapper with default categorization rules
    """
    return CategoryMapper()

