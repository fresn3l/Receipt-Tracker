from datetime import date, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from receipts.models import LineItem, Product, ProductAlias, Receipt
from receipts.product_service import add_alias, resolve_product, set_product_category
from receipts.store_service import normalize_store_name

IMPORTED_IMAGE_PLACEHOLDER = "imported/no-image"


def _parse_date(value: str | None) -> date | None:
    if not value:
        return None
    return date.fromisoformat(value)


def _parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    return datetime.fromisoformat(value)


def import_json_data(db: Session, payload: dict, *, replace: bool = False) -> dict:
    if replace:
        for receipt in db.scalars(select(Receipt)).all():
            db.delete(receipt)
        for product in db.scalars(select(Product)).all():
            db.delete(product)
        db.flush()

    product_id_map: dict[int, int] = {}
    for product_data in payload.get("products", []):
        product = resolve_product(db, product_data["canonical_name"])
        if product_data.get("category"):
            set_product_category(db, product, product_data["category"])
        product.is_watched = bool(product_data.get("is_watched", False))
        product.normalized_unit = product_data.get("normalized_unit")
        product.unit_amount = product_data.get("unit_amount")
        for alias_name in product_data.get("aliases", []):
            add_alias(db, product.id, alias_name)
        if product_data.get("id") is not None:
            product_id_map[product_data["id"]] = product.id

    imported_receipts = 0
    imported_items = 0
    for receipt_data in payload.get("receipts", []):
        purchase_date = _parse_date(receipt_data.get("purchase_date"))
        receipt = Receipt(
            store_name=normalize_store_name(receipt_data.get("store_name")),
            purchase_date=purchase_date,
            total=receipt_data.get("total"),
            image_path=receipt_data.get("image_path") or IMPORTED_IMAGE_PLACEHOLDER,
            image_hash=receipt_data.get("image_hash"),
            notes=receipt_data.get("notes"),
            parse_confidence=receipt_data.get("parse_confidence"),
            reviewed_at=_parse_datetime(receipt_data.get("reviewed_at")),
        )
        db.add(receipt)
        db.flush()
        imported_receipts += 1

        for item_data in receipt_data.get("line_items", []):
            product = resolve_product(db, item_data["raw_name"])
            old_product_id = item_data.get("product_id")
            if old_product_id in product_id_map:
                product = db.get(Product, product_id_map[old_product_id]) or product
            db.add(
                LineItem(
                    receipt_id=receipt.id,
                    product_id=product.id,
                    raw_name=item_data["raw_name"],
                    quantity=item_data.get("quantity", 1.0),
                    unit_price=item_data.get("unit_price"),
                    line_total=item_data.get("line_total"),
                    unit_label=item_data.get("unit_label"),
                    parse_confidence=item_data.get("parse_confidence"),
                )
            )
            imported_items += 1

    db.flush()
    return {
        "imported_receipts": imported_receipts,
        "imported_items": imported_items,
        "imported_products": len(payload.get("products", [])),
    }
