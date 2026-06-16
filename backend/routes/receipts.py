from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from backend.config import RECEIPTS_DIR
from backend.constants import ALLOWED_EXTENSIONS
from backend.database import get_db
from backend.duplicates import find_duplicate_receipts, hash_image
from backend.image_preprocess import preprocess_receipt_image
from backend.models import LineItem, Receipt
from backend.parser import parse_receipt_image
from backend.product_service import cleanup_orphan_products, resolve_product
from backend.receipt_service import (
    apply_parsed_data,
    build_receipt_detail,
    clear_receipt_review,
    delete_receipt_files,
    load_receipt,
    mark_receipt_reviewed,
)
from backend.reparse_service import bulk_reparse_receipts, reparse_candidates
from backend.route_helpers import duplicate_ids, receipt_summary
from backend.schemas import (
    BatchUploadResult,
    BulkReparseRequest,
    BulkReparseResult,
    LineItemCreate,
    LineItemOut,
    LineItemUpdate,
    ReceiptDetail,
    ReceiptSummary,
    ReceiptUpdate,
    ReparseCandidate,
)
from backend.store_service import normalize_store_name

router = APIRouter(tags=["receipts"])


def _list_receipts(db: Session, *, review_only: bool = False) -> list[ReceiptSummary]:
    receipts = db.scalars(
        select(Receipt).options(selectinload(Receipt.line_items)).order_by(Receipt.created_at.desc())
    ).all()
    summaries = [receipt_summary(db, receipt) for receipt in receipts]
    if review_only:
        summaries = [summary for summary in summaries if summary.needs_review]
    return summaries


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
    return build_receipt_detail(receipt, duplicate_ids(db, receipt))


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
    return _list_receipts(db, review_only=review_only)


@router.get("/receipts/review-queue", response_model=list[ReceiptSummary])
def review_queue(db: Session = Depends(get_db)):
    return _list_receipts(db, review_only=True)


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
    return build_receipt_detail(receipt, duplicate_ids(db, receipt))


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
    return build_receipt_detail(receipt, duplicate_ids(db, receipt))


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
    return build_receipt_detail(receipt, duplicate_ids(db, receipt))


@router.post("/receipts/{receipt_id}/mark-reviewed", response_model=ReceiptDetail)
def mark_reviewed(receipt_id: int, db: Session = Depends(get_db)):
    receipt = load_receipt(db, receipt_id)
    if not receipt:
        raise HTTPException(status_code=404, detail="Receipt not found.")
    mark_receipt_reviewed(receipt)
    db.commit()
    receipt = load_receipt(db, receipt_id)
    return build_receipt_detail(receipt, duplicate_ids(db, receipt))


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
