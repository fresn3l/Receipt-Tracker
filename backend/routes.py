import json
from datetime import date
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse, Response
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from backend.analytics import compute_product_analytics, effective_unit_price
from backend.config import RECEIPTS_DIR
from backend.database import get_db
from backend.duplicates import find_duplicate_receipts, hash_image
from backend.export_service import export_csv, export_json
from backend.import_service import import_json_data
from backend.reparse_service import bulk_reparse_receipts, reparse_candidates
from backend.image_preprocess import preprocess_receipt_image
from backend.models import LineItem, Product, ProductAlias, Receipt
from backend.parser import parse_receipt_image
from backend.price_intelligence import (
    get_inflation_basket,
    get_price_alerts,
    get_store_comparison,
    normalized_unit_price,
)
from backend.product_service import (
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
    clear_receipt_review,
    delete_receipt_files,
    load_receipt,
    mark_receipt_reviewed,
    needs_review,
)
from backend.schemas import (
    BatchUploadResult,
    BulkReparseRequest,
    BulkReparseResult,
    BudgetSettings,
    BudgetSettingsUpdate,
    ImportRequest,
    ImportResult,
    InflationBasket,
    LineItemCreate,
    LineItemOut,
    LineItemUpdate,
    MergeSuggestion,
    PriceAlert,
    PricePoint,
    ProductDetail,
    ProductMergeRequest,
    ProductOut,
    ProductUpdate,
    ReceiptDetail,
    ReceiptSummary,
    ReceiptUpdate,
    ReparseCandidate,
    SpendingOverview,
)
from backend.settings_service import get_category_budgets, get_settings
from backend.spending import get_spending_summary, monthly_spend, spend_by_category, spend_by_store
from backend.store_service import normalize_store_name
from backend.validation import validate_receipt

router = APIRouter(prefix="/api", tags=["receipts"])

ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".gif"}
GROCERY_CATEGORIES = [
    "Produce", "Dairy", "Meat", "Seafood", "Bakery", "Frozen",
    "Beverages", "Snacks", "Pantry", "Household", "Personal Care", "Other",
]


def _fetch_product_history(db: Session, product_id: int, product: Product | None = None) -> list[PricePoint]:
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


def _product_summary(db: Session, product: Product) -> ProductOut:
    history = _fetch_product_history(db, product.id, product)
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


def _product_detail(db: Session, product: Product) -> ProductDetail:
    history = _fetch_product_history(db, product.id, product)
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


def _receipt_summary(db: Session, receipt: Receipt) -> ReceiptSummary:
    validation = validate_receipt(receipt.total, receipt.line_items)
    duplicate_ids = _duplicate_ids(db, receipt)
    return ReceiptSummary(
        id=receipt.id,
        store_name=receipt.store_name,
        purchase_date=receipt.purchase_date,
        total=receipt.total,
        created_at=receipt.created_at,
        item_count=len(receipt.line_items),
        has_warning=not validation.is_valid,
        possible_duplicate=bool(duplicate_ids),
        needs_review=needs_review(receipt, validation, duplicate_ids),
        reviewed_at=receipt.reviewed_at,
    )


def _current_month_spend(db: Session) -> float:
    month_key = date.today().strftime("%Y-%m")
    monthly = monthly_spend(db)
    for entry in monthly:
        if entry["month"] == month_key:
            return entry["total"]
    return 0.0


async def _process_upload(file: UploadFile, db: Session) -> ReceiptDetail:
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
            detail=f"This image matches receipt #{existing[0].id}.",
        )

    preprocess_receipt_image(image_path)
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
    return build_receipt_detail(receipt, _duplicate_ids(db, receipt))


@router.post("/receipts/upload", response_model=ReceiptDetail)
async def upload_receipt(file: UploadFile = File(...), db: Session = Depends(get_db)):
    return await _process_upload(file, db)


@router.post("/receipts/upload/batch", response_model=BatchUploadResult)
async def upload_receipt_batch(files: list[UploadFile] = File(...), db: Session = Depends(get_db)):
    saved: list[ReceiptDetail] = []
    failed: list[dict] = []
    for file in files:
        try:
            saved.append(await _process_upload(file, db))
        except HTTPException as exc:
            failed.append({"filename": file.filename, "error": exc.detail})
        except Exception as exc:
            failed.append({"filename": file.filename, "error": str(exc)})
    return BatchUploadResult(saved=saved, failed=failed)


@router.get("/receipts", response_model=list[ReceiptSummary])
def list_receipts(
    review_only: bool = Query(False),
    db: Session = Depends(get_db),
):
    receipts = db.scalars(
        select(Receipt).options(selectinload(Receipt.line_items)).order_by(Receipt.created_at.desc())
    ).all()
    summaries = [_receipt_summary(db, receipt) for receipt in receipts]
    if review_only:
        summaries = [summary for summary in summaries if summary.needs_review]
    return summaries


@router.get("/receipts/review-queue", response_model=list[ReceiptSummary])
def review_queue(db: Session = Depends(get_db)):
    return list_receipts(review_only=True, db=db)


@router.get("/receipts/reparse-candidates", response_model=list[ReparseCandidate])
def list_reparse_candidates(db: Session = Depends(get_db)):
    return reparse_candidates(db)


@router.post("/receipts/reparse/batch", response_model=BulkReparseResult)
def batch_reparse_receipts(payload: BulkReparseRequest, db: Session = Depends(get_db)):
    result = bulk_reparse_receipts(
        db,
        payload.receipt_ids,
        missing_categories_only=payload.missing_categories_only,
    )
    return BulkReparseResult(**result)


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
    if "store_name" in updates:
        updates["store_name"] = normalize_store_name(updates["store_name"])
    for field, value in updates.items():
        setattr(receipt, field, value)
    clear_receipt_review(receipt)

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
    preprocess_receipt_image(image_path)
    try:
        parsed, raw_json = parse_receipt_image(image_path)
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"Failed to parse receipt: {exc}") from exc
    apply_parsed_data(db, receipt, parsed, raw_json)
    db.commit()
    receipt = load_receipt(db, receipt_id)
    return build_receipt_detail(receipt, _duplicate_ids(db, receipt))


@router.post("/receipts/{receipt_id}/mark-reviewed", response_model=ReceiptDetail)
def mark_reviewed(receipt_id: int, db: Session = Depends(get_db)):
    receipt = load_receipt(db, receipt_id)
    if not receipt:
        raise HTTPException(status_code=404, detail="Receipt not found.")
    mark_receipt_reviewed(receipt)
    db.commit()
    receipt = load_receipt(db, receipt_id)
    return build_receipt_detail(receipt, _duplicate_ids(db, receipt))


@router.get("/receipts/{receipt_id}/image")
def get_receipt_image(receipt_id: int, db: Session = Depends(get_db)):
    receipt = db.get(Receipt, receipt_id)
    if not receipt:
        raise HTTPException(status_code=404, detail="Receipt not found.")
    if receipt.image_path == "imported/no-image":
        raise HTTPException(status_code=404, detail="No image for imported receipt.")
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
    clear_receipt_review(receipt)
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
    clear_receipt_review(receipt)
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
    clear_receipt_review(receipt)
    db.commit()
    cleanup_orphan_products(db)
    db.commit()
    return {"ok": True}


@router.get("/products", response_model=list[ProductOut])
def list_products(
    q: str | None = Query(None),
    watched_only: bool = Query(False),
    db: Session = Depends(get_db),
):
    query = select(Product).order_by(Product.canonical_name)
    if q:
        query = query.where(Product.canonical_name.ilike(f"%{q}%"))
    if watched_only:
        query = query.where(Product.is_watched.is_(True))
    products = db.scalars(query).all()
    return [_product_summary(db, product) for product in products]


@router.get("/products/watchlist", response_model=list[ProductOut])
def watchlist(db: Session = Depends(get_db)):
    return list_products(watched_only=True, db=db)


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
    return _product_detail(db, target)


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
    return _product_detail(db, product)


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
    if "is_watched" in updates:
        product.is_watched = updates["is_watched"]
    if "normalized_unit" in updates:
        product.normalized_unit = updates["normalized_unit"]
    if "unit_amount" in updates:
        product.unit_amount = updates["unit_amount"]
    db.commit()
    return get_product(product_id, db)


@router.get("/products/{product_id}/price-history", response_model=list[PricePoint])
def product_price_history(product_id: int, db: Session = Depends(get_db)):
    product = db.get(Product, product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found.")
    return _fetch_product_history(db, product_id)


@router.get("/insights/alerts", response_model=list[PriceAlert])
def price_alerts(db: Session = Depends(get_db)):
    return get_price_alerts(db)


@router.get("/insights/inflation-basket", response_model=InflationBasket)
def inflation_basket(db: Session = Depends(get_db)):
    data = get_inflation_basket(db)
    return InflationBasket(**data)


@router.get("/spending/overview", response_model=SpendingOverview)
def spending_overview(db: Session = Depends(get_db)):
    settings = get_settings(db)
    budget = settings.monthly_budget
    current = _current_month_spend(db)
    remaining = round(budget - current, 2) if budget is not None else None
    return SpendingOverview(
        summary=get_spending_summary(db),
        by_category=spend_by_category(db),
        by_store=spend_by_store(db),
        monthly=monthly_spend(db),
        monthly_budget=budget,
        current_month_spend=round(current, 2),
        budget_remaining=remaining,
    )


@router.get("/settings/budget", response_model=BudgetSettings)
def get_budget_settings(db: Session = Depends(get_db)):
    settings = get_settings(db)
    return BudgetSettings(
        monthly_budget=settings.monthly_budget,
        category_budgets=get_category_budgets(settings),
    )


@router.patch("/settings/budget", response_model=BudgetSettings)
def update_budget_settings(payload: BudgetSettingsUpdate, db: Session = Depends(get_db)):
    settings = get_settings(db)
    updates = payload.model_dump(exclude_unset=True)
    if "monthly_budget" in updates:
        settings.monthly_budget = updates["monthly_budget"]
    if "category_budgets" in updates:
        settings.category_budgets_json = json.dumps(updates["category_budgets"])
    db.commit()
    return BudgetSettings(
        monthly_budget=settings.monthly_budget,
        category_budgets=get_category_budgets(settings),
    )


@router.get("/export/json")
def export_data_json(db: Session = Depends(get_db)):
    return export_json(db)


@router.get("/export/csv")
def export_data_csv(db: Session = Depends(get_db)):
    return Response(
        content=export_csv(db),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=receipts.csv"},
    )


@router.post("/import/json", response_model=ImportResult)
def import_data_json(payload: ImportRequest, db: Session = Depends(get_db)):
    try:
        result = import_json_data(db, payload.data, replace=payload.replace)
        db.commit()
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=f"Import failed: {exc}") from exc
    return ImportResult(**result)


@router.post("/import/json/file", response_model=ImportResult)
async def import_data_json_file(
    file: UploadFile = File(...),
    replace: bool = Query(False),
    db: Session = Depends(get_db),
):
    try:
        payload = json.loads(await file.read())
        result = import_json_data(db, payload, replace=replace)
        db.commit()
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail="Invalid JSON file.") from exc
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=f"Import failed: {exc}") from exc
    return ImportResult(**result)
