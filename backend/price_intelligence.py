from collections import defaultdict

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.analytics import compute_product_analytics, effective_unit_price
from backend.models import LineItem, Product, Receipt
from backend.schemas import PriceAlert, PricePoint, StorePriceComparison


def _history_for_product(db: Session, product_id: int) -> list[PricePoint]:
    rows = db.execute(
        select(LineItem, Receipt.purchase_date, Receipt.id, Receipt.store_name)
        .join(Receipt, LineItem.receipt_id == Receipt.id)
        .where(LineItem.product_id == product_id)
        .order_by(Receipt.purchase_date.asc().nullslast(), Receipt.created_at.asc())
    ).all()
    history: list[PricePoint] = []
    for item, purchase_date, receipt_id, _store in rows:
        point = PricePoint(
            purchase_date=purchase_date,
            unit_price=item.unit_price,
            line_total=item.line_total,
            quantity=item.quantity,
            receipt_id=receipt_id,
        )
        point.effective_price = effective_unit_price(point)
        history.append(point)
    return history


def normalized_unit_price(product: Product, price: float | None) -> float | None:
    if price is None or not product.unit_amount:
        return price
    return round(price / product.unit_amount, 4)


def get_price_alerts(db: Session) -> list[PriceAlert]:
    alerts: list[PriceAlert] = []
    products = db.scalars(select(Product)).all()
    for product in products:
        history = _history_for_product(db, product.id)
        if len(history) < 2:
            continue
        analytics = compute_product_analytics(history)
        prices = [point.effective_price for point in history if point.effective_price is not None]
        if not prices or analytics.latest_price is None:
            continue

        if analytics.change_since_previous_pct is not None and analytics.change_since_previous_pct >= 10:
            alerts.append(
                PriceAlert(
                    product_id=product.id,
                    product_name=product.canonical_name,
                    alert_type="price_increase",
                    message=f"Up {analytics.change_since_previous_pct:.1f}% since last purchase",
                    latest_price=analytics.latest_price,
                    change_pct=analytics.change_since_previous_pct,
                )
            )
        elif analytics.latest_price >= max(prices) and len(prices) >= 3:
            alerts.append(
                PriceAlert(
                    product_id=product.id,
                    product_name=product.canonical_name,
                    alert_type="highest_ever",
                    message="At highest recorded price",
                    latest_price=analytics.latest_price,
                    change_pct=analytics.change_since_previous_pct,
                )
            )
    return sorted(alerts, key=lambda alert: alert.change_pct or 0, reverse=True)


def get_store_comparison(db: Session, product_id: int) -> list[StorePriceComparison]:
    rows = db.execute(
        select(LineItem, Receipt.store_name, Receipt.purchase_date)
        .join(Receipt, LineItem.receipt_id == Receipt.id)
        .where(LineItem.product_id == product_id)
    ).all()

    by_store: dict[str, list[float]] = defaultdict(list)
    for item, store_name, _date in rows:
        store = store_name or "Unknown store"
        point = PricePoint(
            purchase_date=None,
            unit_price=item.unit_price,
            line_total=item.line_total,
            quantity=item.quantity,
            receipt_id=0,
        )
        price = effective_unit_price(point)
        if price is not None:
            by_store[store].append(price)

    results: list[StorePriceComparison] = []
    for store, prices in by_store.items():
        results.append(
            StorePriceComparison(
                store=store,
                purchase_count=len(prices),
                avg_price=round(sum(prices) / len(prices), 2),
                latest_price=round(prices[-1], 2),
            )
        )
    return sorted(results, key=lambda entry: entry.avg_price)


def get_inflation_basket(db: Session) -> dict:
    products = db.scalars(select(Product)).all()
    changes: list[float] = []
    weights: list[int] = []
    for product in products:
        history = _history_for_product(db, product.id)
        analytics = compute_product_analytics(history)
        if analytics.change_since_first_pct is None or analytics.purchase_count < 2:
            continue
        changes.append(analytics.change_since_first_pct)
        weights.append(analytics.purchase_count)

    if not changes:
        return {"basket_change_pct": None, "product_count": 0}

    total_weight = sum(weights)
    weighted = sum(change * weight for change, weight in zip(changes, weights)) / total_weight
    return {
        "basket_change_pct": round(weighted, 1),
        "product_count": len(changes),
    }
