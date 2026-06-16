from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.analytics import compute_product_analytics, effective_unit_price
from backend.duplicates import find_duplicate_receipts
from backend.models import LineItem, Product, ProductAlias, Receipt
from backend.price_intelligence import get_store_comparison, normalized_unit_price
from backend.receipt_service import needs_review
from backend.schemas import PricePoint, ProductDetail, ProductOut, ReceiptSummary
from backend.spending import monthly_spend
from backend.validation import validate_receipt


def fetch_product_history(db: Session, product_id: int, product: Product | None = None) -> list[PricePoint]:
    rows = db.execute(
        select(LineItem, Receipt.purchase_date, Receipt.id, Receipt.created_at)
        .join(Receipt, LineItem.receipt_id == Receipt.id)
        .where(LineItem.product_id == product_id)
        .order_by(Receipt.purchase_date.asc().nullslast(), Receipt.created_at.asc())
    ).all()
    history: list[PricePoint] = []
    if product is None:
        product = db.get(Product, product_id)
    for item, purchase_date, receipt_id, _created_at in rows:
        point = PricePoint(
            purchase_date=purchase_date,
            unit_price=item.unit_price,
            line_total=item.line_total,
            quantity=item.quantity,
            receipt_id=receipt_id,
        )
        point.effective_price = effective_unit_price(point)
        point.normalized_price = normalized_unit_price(product, point.effective_price) if product else None
        history.append(point)
    return history


def product_summary(db: Session, product: Product) -> ProductOut:
    history = fetch_product_history(db, product.id, product)
    analytics = compute_product_analytics(history)
    return ProductOut(
        id=product.id,
        canonical_name=product.canonical_name,
        category=product.category,
        purchase_count=analytics.purchase_count,
        avg_price=analytics.avg_price,
        latest_price=analytics.latest_price,
        change_since_previous_pct=analytics.change_since_previous_pct,
        is_watched=product.is_watched,
        normalized_unit=product.normalized_unit,
        normalized_unit_price=normalized_unit_price(product, analytics.latest_price),
    )


def product_detail(db: Session, product: Product) -> ProductDetail:
    history = fetch_product_history(db, product.id, product)
    analytics = compute_product_analytics(history)
    aliases = db.scalars(select(ProductAlias.alias).where(ProductAlias.product_id == product.id)).all()
    return ProductDetail(
        id=product.id,
        canonical_name=product.canonical_name,
        category=product.category,
        aliases=list(aliases),
        is_watched=product.is_watched,
        normalized_unit=product.normalized_unit,
        unit_amount=product.unit_amount,
        normalized_unit_price=normalized_unit_price(product, analytics.latest_price),
        analytics=analytics,
        history=history,
        store_comparison=get_store_comparison(db, product.id),
    )


def duplicate_ids(db: Session, receipt: Receipt) -> list[int]:
    matches = find_duplicate_receipts(
        db,
        image_hash=receipt.image_hash,
        store_name=receipt.store_name,
        purchase_date=receipt.purchase_date,
        total=receipt.total,
        exclude_id=receipt.id,
    )
    return [match.id for match in matches]


def receipt_summary(db: Session, receipt: Receipt) -> ReceiptSummary:
    validation = validate_receipt(receipt.total, receipt.line_items)
    dup_ids = duplicate_ids(db, receipt)
    return ReceiptSummary(
        id=receipt.id,
        store_name=receipt.store_name,
        purchase_date=receipt.purchase_date,
        total=receipt.total,
        created_at=receipt.created_at,
        item_count=len(receipt.line_items),
        has_warning=not validation.is_valid,
        possible_duplicate=bool(dup_ids),
        needs_review=needs_review(receipt, validation, dup_ids),
        reviewed_at=receipt.reviewed_at,
    )


def current_month_spend(db: Session) -> float:
    month_key = date.today().strftime("%Y-%m")
    for entry in monthly_spend(db):
        if entry["month"] == month_key:
            return entry["total"]
    return 0.0
