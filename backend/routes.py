from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from backend.config import RECEIPTS_DIR
from backend.database import get_db
from backend.models import LineItem, Product, Receipt
from backend.analytics import compute_product_analytics, effective_unit_price
from backend.parser import parse_receipt_image
from backend.receipt_service import (
    apply_parsed_data,
    build_receipt_detail,
    delete_receipt_files,
    get_or_create_product,
    load_receipt,
)
from backend.schemas import (
    LineItemCreate,
    LineItemOut,
    LineItemUpdate,
    PricePoint,
    ProductDetail,
    ProductOut,
    ReceiptDetail,
    ReceiptSummary,
    ReceiptUpdate,
)
from backend.validation import validate_receipt

router = APIRouter(prefix="/api", tags=["receipts"])

ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".gif"}


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

    try:
        parsed, raw_json = parse_receipt_image(image_path)
    except Exception as exc:
        image_path.unlink(missing_ok=True)
        raise HTTPException(status_code=422, detail=f"Failed to parse receipt: {exc}") from exc

    receipt = Receipt(image_path=str(image_path))
    db.add(receipt)
    db.flush()
    apply_parsed_data(db, receipt, parsed, raw_json)
    db.commit()

    receipt = load_receipt(db, receipt.id)
    return build_receipt_detail(receipt)


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
        )
        for r in receipts
    ]


@router.get("/receipts/{receipt_id}", response_model=ReceiptDetail)
def get_receipt(receipt_id: int, db: Session = Depends(get_db)):
    receipt = load_receipt(db, receipt_id)
    if not receipt:
        raise HTTPException(status_code=404, detail="Receipt not found.")
    return build_receipt_detail(receipt)


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
    return build_receipt_detail(receipt)


@router.delete("/receipts/{receipt_id}")
def delete_receipt(receipt_id: int, db: Session = Depends(get_db)):
    receipt = load_receipt(db, receipt_id)
    if not receipt:
        raise HTTPException(status_code=404, detail="Receipt not found.")

    delete_receipt_files(receipt)
    db.delete(receipt)
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
    return build_receipt_detail(receipt)


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

    product = get_or_create_product(db, payload.raw_name)
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
        product = get_or_create_product(db, updates["raw_name"])
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
    return {"ok": True}


@router.get("/products", response_model=list[ProductOut])
def list_products(q: str | None = Query(None), db: Session = Depends(get_db)):
    query = select(Product).order_by(Product.canonical_name)
    if q:
        query = query.where(Product.canonical_name.ilike(f"%{q}%"))
    products = db.scalars(query).all()
    return [_product_summary(db, product) for product in products]


@router.get("/products/{product_id}", response_model=ProductDetail)
def get_product(product_id: int, db: Session = Depends(get_db)):
    product = db.get(Product, product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found.")

    history = _fetch_product_history(db, product_id)
    return ProductDetail(
        id=product.id,
        canonical_name=product.canonical_name,
        category=product.category,
        analytics=compute_product_analytics(history),
        history=history,
    )


@router.get("/products/{product_id}/price-history", response_model=list[PricePoint])
def product_price_history(product_id: int, db: Session = Depends(get_db)):
    product = db.get(Product, product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found.")
    return _fetch_product_history(db, product_id)
