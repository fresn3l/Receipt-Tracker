from datetime import datetime
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from receipts.models import LineItem, Receipt
from receipts.product_service import resolve_product, set_product_category
from receipts.schemas import ParsedReceipt, ReceiptDetail
from receipts.store_service import normalize_store_name
from receipts.validation import validate_receipt

CONFIDENCE_REVIEW_THRESHOLD = 0.75
ITEM_CONFIDENCE_REVIEW_THRESHOLD = 0.7


def clear_line_items(db: Session, receipt: Receipt) -> None:
    for item in list(receipt.line_items):
        db.delete(item)
    db.flush()


def _apply_unit_info(product, item) -> None:
    if item.normalized_unit and not product.normalized_unit:
        product.normalized_unit = item.normalized_unit
    if item.unit_amount and not product.unit_amount:
        product.unit_amount = item.unit_amount


def apply_parsed_data(
    db: Session,
    receipt: Receipt,
    parsed: ParsedReceipt,
    raw_json: str,
) -> Receipt:
    receipt.store_name = normalize_store_name(parsed.store_name)
    receipt.purchase_date = parsed.purchase_date
    receipt.total = parsed.total
    receipt.raw_parse_json = raw_json
    receipt.reviewed_at = None

    confidences = [item.confidence for item in parsed.line_items if item.confidence is not None]
    receipt.parse_confidence = round(sum(confidences) / len(confidences), 2) if confidences else None

    clear_line_items(db, receipt)

    for item in parsed.line_items:
        product = resolve_product(db, item.name)
        if item.category and not product.category:
            set_product_category(db, product, item.category)
        _apply_unit_info(product, item)
        db.add(
            LineItem(
                receipt_id=receipt.id,
                product_id=product.id,
                raw_name=item.name,
                quantity=item.quantity,
                unit_price=item.unit_price,
                line_total=item.line_total,
                unit_label=item.unit_label,
                parse_confidence=item.confidence,
            )
        )

    db.flush()
    return receipt


def load_receipt(db: Session, receipt_id: int) -> Receipt | None:
    return db.scalar(
        select(Receipt).options(selectinload(Receipt.line_items)).where(Receipt.id == receipt_id)
    )


def needs_review(receipt: Receipt, validation, duplicate_ids: list[int]) -> bool:
    if receipt.reviewed_at is not None:
        return False
    if not validation.is_valid or duplicate_ids:
        return True
    if receipt.parse_confidence is not None and receipt.parse_confidence < CONFIDENCE_REVIEW_THRESHOLD:
        return True
    return any(
        item.parse_confidence is not None and item.parse_confidence < ITEM_CONFIDENCE_REVIEW_THRESHOLD
        for item in receipt.line_items
    )


def mark_receipt_reviewed(receipt: Receipt) -> None:
    receipt.reviewed_at = datetime.utcnow()


def clear_receipt_review(receipt: Receipt) -> None:
    receipt.reviewed_at = None


def build_receipt_detail(receipt: Receipt, possible_duplicate_ids: list[int] | None = None) -> ReceiptDetail:
    duplicate_ids = possible_duplicate_ids or []
    validation = validate_receipt(receipt.total, receipt.line_items)
    return ReceiptDetail(
        id=receipt.id,
        store_name=receipt.store_name,
        purchase_date=receipt.purchase_date,
        total=receipt.total,
        image_path=receipt.image_path,
        created_at=receipt.created_at,
        notes=receipt.notes,
        parse_confidence=receipt.parse_confidence,
        reviewed_at=receipt.reviewed_at,
        line_items=receipt.line_items,
        validation=validation,
        possible_duplicate_ids=duplicate_ids,
        needs_review=needs_review(receipt, validation, duplicate_ids),
    )


def delete_receipt_files(receipt: Receipt) -> None:
    if receipt.image_path == "imported/no-image":
        return
    path = Path(receipt.image_path)
    path.unlink(missing_ok=True)
