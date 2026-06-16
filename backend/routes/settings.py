import json

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.schemas import BudgetSettings, BudgetSettingsUpdate
from backend.settings_service import get_category_budgets, get_settings

router = APIRouter(tags=["settings"])


@router.get("/settings/budget", response_model=BudgetSettings)
def get_budget_settings(db: Session = Depends(get_db)):
    settings = get_settings(db)
    return BudgetSettings(
        monthly_budget=settings.monthly_budget,
        category_budgets=get_category_budgets(settings),
    )


@router.patch("/settings/budget", response_model=BudgetSettings)
def update_budget_settings(payload: BudgetSettingsUpdate, db: Session = Depends(get_db)):
    settings = get_settings(db)
    updates = payload.model_dump(exclude_unset=True)
    if "monthly_budget" in updates:
        settings.monthly_budget = updates["monthly_budget"]
    if "category_budgets" in updates:
        settings.category_budgets_json = json.dumps(updates["category_budgets"])
    db.commit()
    return BudgetSettings(
        monthly_budget=settings.monthly_budget,
        category_budgets=get_category_budgets(settings),
    )
