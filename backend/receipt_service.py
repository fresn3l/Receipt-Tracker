from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from backend.models import LineItem, Receipt
from backend.product_service import resolve_product, set_product_category
from backend.schemas import ParsedReceipt, ReceiptDetail
from backend.validation import validate_receipt


def clear_line_items(db: Session, receipt: Receipt) -> None:
    for item in list(receipt.line_items):
        db.delete(item)
    db.flush()


def apply_parsed_data(
    db: Session,
    receipt: Receipt,
    parsed: ParsedReceipt,
    raw_json: str,
) -> Receipt:
    receipt.store_name = parsed.store_name
    receipt.purchase_date = parsed.purchase_date
    receipt.total = parsed.total
    receipt.raw_parse_json = raw_json

    clear_line_items(db, receipt)

    for item in parsed.line_items:
        product = resolve_product(db, item.name)
        if item.category and not product.category:
            set_product_category(db, product, item.category)
        db.add(
            LineItem(
                receipt_id=receipt.id,
                product_id=product.id,
                raw_name=item.name,
                quantity=item.quantity,
                unit_price=item.unit_price,
                line_total=item.line_total,
            )
        )

    db.flush()
    return receipt


def load_receipt(db: Session, receipt_id: int) -> Receipt | None:
    return db.scalar(
        select(Receipt).options(selectinload(Receipt.line_items)).where(Receipt.id == receipt_id)
    )


def build_receipt_detail(receipt: Receipt, possible_duplicate_ids: list[int] | None = None) -> ReceiptDetail:
    validation = validate_receipt(receipt.total, receipt.line_items)
    return ReceiptDetail(
        id=receipt.id,
        store_name=receipt.store_name,
        purchase_date=receipt.purchase_date,
        total=receipt.total,
        image_path=receipt.image_path,
        created_at=receipt.created_at,
        line_items=receipt.line_items,
        validation=validation,
        possible_duplicate_ids=possible_duplicate_ids or [],
    )


def delete_receipt_files(receipt: Receipt) -> None:
    path = Path(receipt.image_path)
    path.unlink(missing_ok=True)
