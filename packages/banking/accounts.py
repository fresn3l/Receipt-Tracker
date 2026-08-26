"""Named bank accounts (checking, credit cards, etc.)."""

from __future__ import annotations

import json
import logging
import uuid
from enum import Enum
from pathlib import Path
from typing import List, Optional

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class AccountType(str, Enum):
    CHECKING = "checking"
    CREDIT_CARD = "credit_card"
    SAVINGS = "savings"
    OTHER = "other"


class Account(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    account_type: AccountType = AccountType.OTHER


class AccountRepository:
    """Persist accounts in accounts.json under the bank data dir."""

    def __init__(self, data_dir: Path):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.path = self.data_dir / "accounts.json"

    def load_all(self) -> List[Account]:
        if not self.path.exists():
            return []
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
            return [Account.model_validate(item) for item in raw]
        except Exception as exc:
            logger.warning("Failed to load accounts: %s", exc)
            return []

    def save_all(self, accounts: List[Account]) -> None:
        payload = [a.model_dump() for a in accounts]
        self.path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def get(self, account_id: str) -> Optional[Account]:
        return next((a for a in self.load_all() if a.id == account_id), None)

    def find_by_name(self, name: str) -> Optional[Account]:
        needle = name.strip().lower()
        return next((a for a in self.load_all() if a.name.strip().lower() == needle), None)

    def upsert(self, account: Account) -> Account:
        accounts = self.load_all()
        for i, existing in enumerate(accounts):
            if existing.id == account.id or existing.name.strip().lower() == account.name.strip().lower():
                accounts[i] = account
                self.save_all(accounts)
                return account
        accounts.append(account)
        self.save_all(accounts)
        return account

    def delete(self, account_id: str) -> bool:
        accounts = self.load_all()
        kept = [a for a in accounts if a.id != account_id]
        if len(kept) == len(accounts):
            return False
        self.save_all(kept)
        return True

    def ensure_defaults(self) -> List[Account]:
        """Create Checking + two credit cards if the registry is empty."""
        existing = self.load_all()
        if existing:
            return existing
        defaults = [
            Account(name="Checking", account_type=AccountType.CHECKING),
            Account(name="Credit Card 1", account_type=AccountType.CREDIT_CARD),
            Account(name="Credit Card 2", account_type=AccountType.CREDIT_CARD),
        ]
        self.save_all(defaults)
        return defaults
