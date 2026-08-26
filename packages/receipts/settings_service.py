import json
from pathlib import Path

from sqlalchemy.orm import Session

from receipts.models import AppSettings


def get_settings(db: Session) -> AppSettings:
    settings = db.get(AppSettings, 1)
    if not settings:
        settings = AppSettings(id=1)
        db.add(settings)
        db.flush()
    return settings


def get_category_budgets(settings: AppSettings) -> dict[str, float]:
    if not settings.category_budgets_json:
        return {}
    return json.loads(settings.category_budgets_json)


def update_settings(
    db: Session,
    monthly_budget: float | None = None,
    category_budgets: dict[str, float] | None = None,
) -> AppSettings:
    settings = get_settings(db)
    if monthly_budget is not None:
        settings.monthly_budget = monthly_budget
    if category_budgets is not None:
        settings.category_budgets_json = json.dumps(category_budgets)
    db.flush()
    return settings
