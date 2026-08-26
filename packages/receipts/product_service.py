import json
from difflib import SequenceMatcher

from openai import OpenAI
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from receipts.config import settings
from receipts.models import LineItem, Product, ProductAlias
from receipts.parser import normalize_product_name


def _similarity(left: str, right: str) -> float:
    return SequenceMatcher(None, left.lower(), right.lower()).ratio()


def resolve_product(db: Session, raw_name: str) -> Product:
    canonical = normalize_product_name(raw_name)
    alias = db.scalar(
        select(ProductAlias).where(func.lower(ProductAlias.alias) == canonical.lower())
    )
    if alias:
        return alias.product

    product = db.scalar(
        select(Product).where(func.lower(Product.canonical_name) == canonical.lower())
    )
    if product:
        return product

    product = Product(canonical_name=canonical)
    db.add(product)
    db.flush()
    return product


def add_alias(db: Session, product_id: int, alias: str) -> ProductAlias:
    cleaned = normalize_product_name(alias)
    existing = db.scalar(select(ProductAlias).where(func.lower(ProductAlias.alias) == cleaned.lower()))
    if existing:
        if existing.product_id != product_id:
            raise ValueError(f"Alias '{cleaned}' already belongs to another product.")
        return existing

    record = ProductAlias(product_id=product_id, alias=cleaned)
    db.add(record)
    db.flush()
    return record


def merge_products(db: Session, target_id: int, source_ids: list[int]) -> Product:
    target = db.get(Product, target_id)
    if not target:
        raise ValueError("Target product not found.")

    unique_sources = [sid for sid in source_ids if sid != target_id]
    for source_id in unique_sources:
        source = db.get(Product, source_id)
        if not source:
            continue

        for item in db.scalars(select(LineItem).where(LineItem.product_id == source_id)).all():
            item.product_id = target_id

        add_alias(db, target_id, source.canonical_name)
        for alias in db.scalars(select(ProductAlias).where(ProductAlias.product_id == source_id)).all():
            add_alias(db, target_id, alias.alias)
            db.delete(alias)

        db.delete(source)

    db.flush()
    cleanup_orphan_products(db)
    return target


def cleanup_orphan_products(db: Session) -> int:
    used_ids = {
        product_id
        for product_id in db.scalars(select(LineItem.product_id).where(LineItem.product_id.is_not(None))).all()
        if product_id is not None
    }
    removed = 0
    for product in db.scalars(select(Product)).all():
        if product.id not in used_ids:
            for alias in db.scalars(select(ProductAlias).where(ProductAlias.product_id == product.id)).all():
                db.delete(alias)
            db.delete(product)
            removed += 1
    db.flush()
    return removed


def find_merge_suggestions(db: Session, threshold: float = 0.72) -> list[dict]:
    products = db.scalars(select(Product).order_by(Product.canonical_name)).all()
    suggestions: list[dict] = []
    seen: set[frozenset[int]] = set()

    for i, left in enumerate(products):
        for right in products[i + 1 :]:
            score = _similarity(left.canonical_name, right.canonical_name)
            if score < threshold:
                continue
            key = frozenset({left.id, right.id})
            if key in seen:
                continue
            seen.add(key)
            suggestions.append(
                {
                    "product_ids": [left.id, right.id],
                    "names": [left.canonical_name, right.canonical_name],
                    "score": round(score, 2),
                    "reason": "similar names",
                }
            )

    suggestions.sort(key=lambda entry: entry["score"], reverse=True)
    return suggestions


def suggest_merges_with_llm(db: Session) -> list[dict]:
    if not settings.openai_api_key:
        raise ValueError("OPENAI_API_KEY is not set.")

    products = db.scalars(select(Product).order_by(Product.canonical_name)).all()
    if len(products) < 2:
        return []

    names = [product.canonical_name for product in products]
    client = OpenAI(api_key=settings.openai_api_key)
    response = client.chat.completions.create(
        model=settings.openai_model,
        response_format={"type": "json_object"},
        messages=[
            {
                "role": "user",
                "content": (
                    "Group grocery product names that refer to the same real-world item. "
                    "Return JSON: {\"groups\": [[\"name1\", \"name2\"], ...]}. "
                    "Only include groups with 2+ names you are confident about. Names:\n"
                    + json.dumps(names)
                ),
            }
        ],
        max_tokens=2048,
    )
    payload = json.loads(response.choices[0].message.content or "{}")
    name_to_id = {product.canonical_name.lower(): product.id for product in products}
    suggestions: list[dict] = []

    for group in payload.get("groups", []):
        ids = []
        group_names = []
        for name in group:
            product_id = name_to_id.get(str(name).lower())
            if product_id:
                ids.append(product_id)
                group_names.append(name)
        if len(ids) >= 2:
            suggestions.append(
                {
                    "product_ids": ids,
                    "names": group_names,
                    "score": 1.0,
                    "reason": "AI suggested",
                }
            )

    return suggestions


def set_product_category(db: Session, product: Product, category: str | None) -> None:
    if category:
        product.category = normalize_product_name(category)
    else:
        product.category = None
