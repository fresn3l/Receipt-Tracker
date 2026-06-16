from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.price_intelligence import get_inflation_basket, get_price_alerts
from backend.schemas import InflationBasket, PriceAlert

router = APIRouter(tags=["insights"])


@router.get("/insights/alerts", response_model=list[PriceAlert])
def price_alerts(db: Session = Depends(get_db)):
    return get_price_alerts(db)


@router.get("/insights/inflation-basket", response_model=InflationBasket)
def inflation_basket(db: Session = Depends(get_db)):
    data = get_inflation_basket(db)
    return InflationBasket(**data)
