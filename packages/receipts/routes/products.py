from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from receipts.constants import GROCERY_CATEGORIES
from receipts.database import get_db
from receipts.models import Product
from receipts.product_service import (
    cleanup_orphan_products,
    find_merge_suggestions,
    merge_products,
    set_product_category,
    suggest_merges_with_llm,
)
from receipts.route_helpers import fetch_product_history, product_detail, product_summary
from receipts.schemas import MergeSuggestion, PricePoint, ProductDetail, ProductMergeRequest, ProductOut, ProductUpdate

router = APIRouter(tags=["products"])


def _list_products(
    db: Session,
    *,
    q: str | None = None,
    watched_only: bool = False,
) -> list[ProductOut]:
    query = select(Product).order_by(Product.canonical_name)
    if q:
        query = query.where(Product.canonical_name.ilike(f"%{q}%"))
    if watched_only:
        query = query.where(Product.is_watched.is_(True))
    products = db.scalars(query).all()
    return [product_summary(db, product) for product in products]


@router.get("/products", response_model=list[ProductOut])
def list_products(
    q: str | None = Query(None),
    watched_only: bool = Query(False),
    db: Session = Depends(get_db),
):
    return _list_products(db, q=q, watched_only=watched_only)


@router.get("/products/watchlist", response_model=list[ProductOut])
def watchlist(db: Session = Depends(get_db)):
    return _list_products(db, watched_only=True)


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
    return product_detail(db, target)


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
    return product_detail(db, product)


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
    return fetch_product_history(db, product_id)
