from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from backend.analytics import compute_product_analytics, effective_unit_price
from backend.config import RECEIPTS_DIR
from backend.database import get_db
from backend.duplicates import find_duplicate_receipts, hash_image
from backend.models import LineItem, Product, ProductAlias, Receipt
from backend.parser import parse_receipt_image
from backend.product_service import (
    add_alias,
    cleanup_orphan_products,
    find_merge_suggestions,
    merge_products,
    resolve_product,
    set_product_category,
    suggest_merges_with_llm,
)
from backend.receipt_service import (
    apply_parsed_data,
    build_receipt_detail,
    delete_receipt_files,
    load_receipt,
)
from backend.schemas import (
    LineItemCreate,
    LineItemOut,
    LineItemUpdate,
    MergeSuggestion,
    PricePoint,
    ProductDetail,
    ProductMergeRequest,
    ProductOut,
    ProductUpdate,
    ReceiptDetail,
    ReceiptSummary,
    ReceiptUpdate,
    SpendingOverview,
)
from backend.spending import (
    get_spending_summary,
    monthly_spend,
    spend_by_category,
    spend_by_store,
)
from backend.validation import validate_receipt

router = APIRouter(prefix="/api", tags=["receipts"])

ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".gif"}
GROCERY_CATEGORIES = [
    "Produce",
    "Dairy",
    "Meat",
    "Seafood",
    "Bakery",
    "Frozen",
    "Beverages",
    "Snacks",
    "Pantry",
    "Household",
    "Personal Care",
    "Other",
]


def _fetch_product_history(db: Session, product_id: int) -> list[PricePoint]:
    rows = db.execute(
        select(LineItem, Receipt.purchase_date, Receipt.id, Receipt.created_at)
        .join(Receipt, LineItem.receipt_id == Receipt.id)
        .where(LineItem.product_id == product_id)
        .order_by(Receipt.purchase_date.asc().nullslast(), Receipt.created_at.asc())
    ).all()

    history: list[PricePoint] = []
    for item, purchase_date, receipt_id, _created_at in rows:
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


def _product_summary(db: Session, product: Product) -> ProductOut:
    history = _fetch_product_history(db, product.id)
    analytics = compute_product_analytics(history)
    return ProductOut(
        id=product.id,
        canonical_name=product.canonical_name,
        category=product.category,
        purchase_count=analytics.purchase_count,
        avg_price=analytics.avg_price,
        latest_price=analytics.latest_price,
        change_since_previous_pct=analytics.change_since_previous_pct,
    )


def _duplicate_ids(db: Session, receipt: Receipt) -> list[int]:
    matches = find_duplicate_receipts(
        db,
        image_hash=receipt.image_hash,
        store_name=receipt.store_name,
        purchase_date=receipt.purchase_date,
        total=receipt.total,
        exclude_id=receipt.id,
    )
    return [match.id for match in matches]


def _has_duplicate(db: Session, receipt: Receipt) -> bool:
    return bool(_duplicate_ids(db, receipt))


@router.post("/receipts/upload", response_model=ReceiptDetail)
async def upload_receipt(file: UploadFile = File(...), db: Session = Depends(get_db)):
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail="Upload a JPG, PNG, or WEBP image.")

    RECEIPTS_DIR.mkdir(parents=True, exist_ok=True)
    filename = f"{uuid4().hex}{suffix}"
    image_path = RECEIPTS_DIR / filename

    contents = await file.read()
    image_path.write_bytes(contents)
    image_digest = hash_image(contents)

    existing = find_duplicate_receipts(db, image_hash=image_digest)
    if existing:
        image_path.unlink(missing_ok=True)
        raise HTTPException(
            status_code=409,
            detail=f"This image matches receipt #{existing[0].id}. Delete the duplicate or upload a different photo.",
        )

    try:
        parsed, raw_json = parse_receipt_image(image_path)
    except Exception as exc:
        image_path.unlink(missing_ok=True)
        raise HTTPException(status_code=422, detail=f"Failed to parse receipt: {exc}") from exc

    receipt = Receipt(image_path=str(image_path), image_hash=image_digest)
    db.add(receipt)
    db.flush()
    apply_parsed_data(db, receipt, parsed, raw_json)
    db.commit()

    receipt = load_receipt(db, receipt.id)
    duplicate_ids = _duplicate_ids(db, receipt)
    return build_receipt_detail(receipt, duplicate_ids)


@router.get("/receipts", response_model=list[ReceiptSummary])
def list_receipts(db: Session = Depends(get_db)):
    receipts = db.scalars(
        select(Receipt).options(selectinload(Receipt.line_items)).order_by(Receipt.created_at.desc())
    ).all()
    return [
        ReceiptSummary(
            id=r.id,
            store_name=r.store_name,
            purchase_date=r.purchase_date,
            total=r.total,
            created_at=r.created_at,
            item_count=len(r.line_items),
            has_warning=not validate_receipt(r.total, r.line_items).is_valid,
            possible_duplicate=_has_duplicate(db, r),
        )
        for r in receipts
    ]


@router.get("/receipts/{receipt_id}", response_model=ReceiptDetail)
def get_receipt(receipt_id: int, db: Session = Depends(get_db)):
    receipt = load_receipt(db, receipt_id)
    if not receipt:
        raise HTTPException(status_code=404, detail="Receipt not found.")
    return build_receipt_detail(receipt, _duplicate_ids(db, receipt))


@router.patch("/receipts/{receipt_id}", response_model=ReceiptDetail)
def update_receipt(receipt_id: int, payload: ReceiptUpdate, db: Session = Depends(get_db)):
    receipt = load_receipt(db, receipt_id)
    if not receipt:
        raise HTTPException(status_code=404, detail="Receipt not found.")

    updates = payload.model_dump(exclude_unset=True)
    for field, value in updates.items():
        setattr(receipt, field, value)

    db.commit()
    receipt = load_receipt(db, receipt_id)
    return build_receipt_detail(receipt, _duplicate_ids(db, receipt))


@router.delete("/receipts/{receipt_id}")
def delete_receipt(receipt_id: int, db: Session = Depends(get_db)):
    receipt = load_receipt(db, receipt_id)
    if not receipt:
        raise HTTPException(status_code=404, detail="Receipt not found.")

    delete_receipt_files(receipt)
    db.delete(receipt)
    db.commit()
    cleanup_orphan_products(db)
    db.commit()
    return {"ok": True}


@router.post("/receipts/{receipt_id}/reparse", response_model=ReceiptDetail)
def reparse_receipt(receipt_id: int, db: Session = Depends(get_db)):
    receipt = load_receipt(db, receipt_id)
    if not receipt:
        raise HTTPException(status_code=404, detail="Receipt not found.")

    image_path = Path(receipt.image_path)
    if not image_path.exists():
        raise HTTPException(status_code=404, detail="Receipt image file is missing.")

    try:
        parsed, raw_json = parse_receipt_image(image_path)
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"Failed to parse receipt: {exc}") from exc

    apply_parsed_data(db, receipt, parsed, raw_json)
    db.commit()
    receipt = load_receipt(db, receipt_id)
    return build_receipt_detail(receipt, _duplicate_ids(db, receipt))


@router.get("/receipts/{receipt_id}/image")
def get_receipt_image(receipt_id: int, db: Session = Depends(get_db)):
    receipt = db.get(Receipt, receipt_id)
    if not receipt:
        raise HTTPException(status_code=404, detail="Receipt not found.")
    path = Path(receipt.image_path)
    if not path.exists():
        raise HTTPException(status_code=404, detail="Image file missing.")
    return FileResponse(path)


@router.post("/receipts/{receipt_id}/items", response_model=LineItemOut)
def add_line_item(receipt_id: int, payload: LineItemCreate, db: Session = Depends(get_db)):
    receipt = load_receipt(db, receipt_id)
    if not receipt:
        raise HTTPException(status_code=404, detail="Receipt not found.")

    product = resolve_product(db, payload.raw_name)
    item = LineItem(
        receipt_id=receipt.id,
        product_id=product.id,
        raw_name=payload.raw_name,
        quantity=payload.quantity,
        unit_price=payload.unit_price,
        line_total=payload.line_total,
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@router.patch("/receipts/{receipt_id}/items/{item_id}", response_model=LineItemOut)
def update_line_item(
    receipt_id: int,
    item_id: int,
    payload: LineItemUpdate,
    db: Session = Depends(get_db),
):
    receipt = load_receipt(db, receipt_id)
    if not receipt:
        raise HTTPException(status_code=404, detail="Receipt not found.")

    item = next((entry for entry in receipt.line_items if entry.id == item_id), None)
    if not item:
        raise HTTPException(status_code=404, detail="Line item not found.")

    updates = payload.model_dump(exclude_unset=True)
    if "raw_name" in updates:
        product = resolve_product(db, updates["raw_name"])
        item.product_id = product.id
        item.raw_name = updates["raw_name"]

    for field in ("quantity", "unit_price", "line_total"):
        if field in updates:
            setattr(item, field, updates[field])

    db.commit()
    db.refresh(item)
    return item


@router.delete("/receipts/{receipt_id}/items/{item_id}")
def delete_line_item(receipt_id: int, item_id: int, db: Session = Depends(get_db)):
    receipt = load_receipt(db, receipt_id)
    if not receipt:
        raise HTTPException(status_code=404, detail="Receipt not found.")

    item = next((entry for entry in receipt.line_items if entry.id == item_id), None)
    if not item:
        raise HTTPException(status_code=404, detail="Line item not found.")

    db.delete(item)
    db.commit()
    cleanup_orphan_products(db)
    db.commit()
    return {"ok": True}


@router.get("/products", response_model=list[ProductOut])
def list_products(q: str | None = Query(None), db: Session = Depends(get_db)):
    query = select(Product).order_by(Product.canonical_name)
    if q:
        query = query.where(Product.canonical_name.ilike(f"%{q}%"))
    products = db.scalars(query).all()
    return [_product_summary(db, product) for product in products]


@router.get("/products/merge-suggestions", response_model=list[MergeSuggestion])
def merge_suggestions(use_llm: bool = Query(False), db: Session = Depends(get_db)):
    if use_llm:
        try:
            return suggest_merges_with_llm(db)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
    return find_merge_suggestions(db)


@router.post("/products/merge", response_model=ProductDetail)
def merge_products_endpoint(payload: ProductMergeRequest, db: Session = Depends(get_db)):
    if not payload.source_ids:
        raise HTTPException(status_code=400, detail="Select at least one product to merge.")
    try:
        target = merge_products(db, payload.target_id, payload.source_ids)
        db.commit()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    history = _fetch_product_history(db, target.id)
    aliases = db.scalars(select(ProductAlias.alias).where(ProductAlias.product_id == target.id)).all()
    return ProductDetail(
        id=target.id,
        canonical_name=target.canonical_name,
        category=target.category,
        aliases=list(aliases),
        analytics=compute_product_analytics(history),
        history=history,
    )


@router.post("/products/cleanup-orphans")
def cleanup_orphans(db: Session = Depends(get_db)):
    removed = cleanup_orphan_products(db)
    db.commit()
    return {"removed": removed}


@router.get("/products/categories")
def list_categories():
    return GROCERY_CATEGORIES


@router.get("/products/{product_id}", response_model=ProductDetail)
def get_product(product_id: int, db: Session = Depends(get_db)):
    product = db.get(Product, product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found.")

    history = _fetch_product_history(db, product_id)
    aliases = db.scalars(select(ProductAlias.alias).where(ProductAlias.product_id == product_id)).all()
    return ProductDetail(
        id=product.id,
        canonical_name=product.canonical_name,
        category=product.category,
        aliases=list(aliases),
        analytics=compute_product_analytics(history),
        history=history,
    )


@router.patch("/products/{product_id}", response_model=ProductDetail)
def update_product(product_id: int, payload: ProductUpdate, db: Session = Depends(get_db)):
    product = db.get(Product, product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found.")

    updates = payload.model_dump(exclude_unset=True)
    if "canonical_name" in updates and updates["canonical_name"]:
        product.canonical_name = updates["canonical_name"].strip()
    if "category" in updates:
        set_product_category(db, product, updates["category"])

    db.commit()
    return get_product(product_id, db)


@router.get("/products/{product_id}/price-history", response_model=list[PricePoint])
def product_price_history(product_id: int, db: Session = Depends(get_db)):
    product = db.get(Product, product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found.")
    return _fetch_product_history(db, product_id)


@router.get("/spending/overview", response_model=SpendingOverview)
def spending_overview(db: Session = Depends(get_db)):
    return SpendingOverview(
        summary=get_spending_summary(db),
        by_category=spend_by_category(db),
        by_store=spend_by_store(db),
        monthly=monthly_spend(db),
    )
