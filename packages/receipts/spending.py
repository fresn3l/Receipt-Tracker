from collections import defaultdict
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from receipts.models import LineItem, Product, Receipt

UNCATEGORIZED = "Uncategorized"


def _line_amount(item: LineItem) -> float:
    if item.line_total is not None:
        return item.line_total
    if item.unit_price is not None:
        return item.unit_price * item.quantity
    return 0.0


def _month_key(value: date | None) -> str | None:
    if not value:
        return None
    return f"{value.year:04d}-{value.month:02d}"


def get_spending_summary(db: Session) -> dict:
    receipts = db.scalars(select(Receipt)).all()
    totals = [receipt.total for receipt in receipts if receipt.total is not None]
    item_counts = [len(receipt.line_items) for receipt in receipts]

    return {
        "receipt_count": len(receipts),
        "total_spent": round(sum(totals), 2) if totals else 0.0,
        "avg_trip_total": round(sum(totals) / len(totals), 2) if totals else None,
        "avg_items_per_trip": round(sum(item_counts) / len(item_counts), 1) if item_counts else None,
    }


def spend_by_category(db: Session) -> list[dict]:
    rows = db.execute(
        select(LineItem, Product.category)
        .outerjoin(Product, LineItem.product_id == Product.id)
    ).all()

    totals: dict[str, float] = defaultdict(float)
    for item, category in rows:
        label = category or UNCATEGORIZED
        totals[label] += _line_amount(item)

    return [
        {"category": category, "total": round(amount, 2)}
        for category, amount in sorted(totals.items(), key=lambda entry: entry[1], reverse=True)
    ]


def spend_by_store(db: Session) -> list[dict]:
    receipts = db.scalars(select(Receipt)).all()
    totals: dict[str, float] = defaultdict(float)
    counts: dict[str, int] = defaultdict(int)

    for receipt in receipts:
        store = receipt.store_name or "Unknown store"
        counts[store] += 1
        if receipt.total is not None:
            totals[store] += receipt.total
        else:
            totals[store] += sum(_line_amount(item) for item in receipt.line_items)

    return [
        {
            "store": store,
            "total": round(totals[store], 2),
            "trip_count": counts[store],
        }
        for store in sorted(totals, key=totals.get, reverse=True)
    ]


def monthly_spend(db: Session) -> list[dict]:
    receipts = db.scalars(select(Receipt)).all()
    totals: dict[str, float] = defaultdict(float)
    counts: dict[str, int] = defaultdict(int)

    for receipt in receipts:
        month = _month_key(receipt.purchase_date)
        if not month:
            continue
        counts[month] += 1
        if receipt.total is not None:
            totals[month] += receipt.total
        else:
            totals[month] += sum(_line_amount(item) for item in receipt.line_items)

    return [
        {
            "month": month,
            "total": round(totals[month], 2),
            "trip_count": counts[month],
        }
        for month in sorted(totals)
    ]
