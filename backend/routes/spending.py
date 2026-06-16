from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.route_helpers import current_month_spend
from backend.schemas import SpendingOverview
from backend.settings_service import get_settings
from backend.spending import get_spending_summary, monthly_spend, spend_by_category, spend_by_store

router = APIRouter(tags=["spending"])


@router.get("/spending/overview", response_model=SpendingOverview)
def spending_overview(db: Session = Depends(get_db)):
    settings = get_settings(db)
    budget = settings.monthly_budget
    current = current_month_spend(db)
    remaining = round(budget - current, 2) if budget is not None else None
    return SpendingOverview(
        summary=get_spending_summary(db),
        by_category=spend_by_category(db),
        by_store=spend_by_store(db),
        monthly=monthly_spend(db),
        monthly_budget=budget,
        current_month_spend=round(current, 2),
        budget_remaining=remaining,
    )
