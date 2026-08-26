from pathlib import Path

from sqlalchemy import or_, select
from sqlalchemy.orm import Session, selectinload

from receipts.image_preprocess import preprocess_receipt_image
from receipts.models import LineItem, Product, Receipt
from receipts.parser import parse_receipt_image
from receipts.receipt_service import apply_parsed_data, load_receipt


def receipts_missing_categories(db: Session) -> list[Receipt]:
    receipts = db.scalars(
        select(Receipt).options(selectinload(Receipt.line_items)).order_by(Receipt.created_at.desc())
    ).all()
    results: list[Receipt] = []
    for receipt in receipts:
        product_ids = {item.product_id for item in receipt.line_items if item.product_id}
        if not product_ids:
            continue
        products = db.scalars(select(Product).where(Product.id.in_(product_ids))).all()
        if any(not product.category for product in products):
            results.append(receipt)
    return results


def reparse_candidates(db: Session) -> list[dict]:
    receipts = db.scalars(select(Receipt).order_by(Receipt.created_at.desc())).all()
    candidates: list[dict] = []
    for receipt in receipts:
        path = Path(receipt.image_path)
        if not path.exists() or receipt.image_path == "imported/no-image":
            continue
        missing_categories = False
        product_ids = {item.product_id for item in receipt.line_items if item.product_id}
        if product_ids:
            products = db.scalars(select(Product).where(Product.id.in_(product_ids))).all()
            missing_categories = any(not product.category for product in products)
        candidates.append(
            {
                "id": receipt.id,
                "store_name": receipt.store_name,
                "purchase_date": receipt.purchase_date,
                "missing_categories": missing_categories,
                "parse_confidence": receipt.parse_confidence,
            }
        )
    return candidates


def bulk_reparse_receipts(
    db: Session,
    receipt_ids: list[int] | None = None,
    *,
    missing_categories_only: bool = False,
) -> dict:
    query = select(Receipt).options(selectinload(Receipt.line_items))
    if receipt_ids:
        query = query.where(Receipt.id.in_(receipt_ids))
    receipts = db.scalars(query).all()

    if missing_categories_only:
        receipts = [r for r in receipts if r in receipts_missing_categories(db)]

    succeeded: list[int] = []
    failed: list[dict] = []

    for receipt in receipts:
        path = Path(receipt.image_path)
        if not path.exists():
            failed.append({"id": receipt.id, "error": "Image file missing."})
            continue
        try:
            preprocess_receipt_image(path)
            parsed, raw_json = parse_receipt_image(path)
            apply_parsed_data(db, receipt, parsed, raw_json)
            receipt.reviewed_at = None
            db.commit()
            succeeded.append(receipt.id)
        except Exception as exc:
            db.rollback()
            failed.append({"id": receipt.id, "error": str(exc)})

    return {"succeeded": succeeded, "failed": failed, "total": len(receipts)}
