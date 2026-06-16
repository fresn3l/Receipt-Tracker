import csv
import io
import json
from datetime import date, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from backend.models import LineItem, Product, Receipt


def export_json(db: Session) -> dict:
    receipts = db.scalars(select(Receipt).options(selectinload(Receipt.line_items))).all()
    products = db.scalars(select(Product)).all()
    return {
        "exported_at": datetime.utcnow().isoformat(),
        "receipts": [
            {
                "id": r.id,
                "store_name": r.store_name,
                "purchase_date": r.purchase_date.isoformat() if r.purchase_date else None,
                "total": r.total,
                "notes": r.notes,
                "line_items": [
                    {
                        "raw_name": item.raw_name,
                        "quantity": item.quantity,
                        "unit_price": item.unit_price,
                        "line_total": item.line_total,
                        "product_id": item.product_id,
                    }
                    for item in r.line_items
                ],
            }
            for r in receipts
        ],
        "products": [
            {
                "id": p.id,
                "canonical_name": p.canonical_name,
                "category": p.category,
                "is_watched": p.is_watched,
            }
            for p in products
        ],
    }


def export_csv(db: Session) -> str:
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(
        ["receipt_id", "store", "date", "receipt_total", "item", "qty", "unit_price", "line_total", "category"]
    )
    rows = db.execute(
        select(LineItem, Receipt, Product.category)
        .join(Receipt, LineItem.receipt_id == Receipt.id)
        .outerjoin(Product, LineItem.product_id == Product.id)
        .order_by(Receipt.purchase_date.asc().nullslast())
    ).all()
    for item, receipt, category in rows:
        writer.writerow(
            [
                receipt.id,
                receipt.store_name,
                receipt.purchase_date.isoformat() if receipt.purchase_date else "",
                receipt.total,
                item.raw_name,
                item.quantity,
                item.unit_price,
                item.line_total,
                category or "",
            ]
        )
    return output.getvalue()
