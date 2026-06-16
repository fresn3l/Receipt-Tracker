import hashlib

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.models import Receipt

TOTAL_TOLERANCE = 0.10


def hash_image(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def find_duplicate_receipts(
    db: Session,
    *,
    image_hash: str | None = None,
    store_name: str | None = None,
    purchase_date=None,
    total: float | None = None,
    exclude_id: int | None = None,
) -> list[Receipt]:
    matches: dict[int, Receipt] = {}

    if image_hash:
        query = select(Receipt).where(Receipt.image_hash == image_hash)
        if exclude_id:
            query = query.where(Receipt.id != exclude_id)
        for receipt in db.scalars(query).all():
            matches[receipt.id] = receipt

    if store_name and purchase_date is not None and total is not None:
        candidates = db.scalars(select(Receipt).where(Receipt.purchase_date == purchase_date)).all()
        normalized_store = store_name.strip().lower()
        for receipt in candidates:
            if exclude_id and receipt.id == exclude_id:
                continue
            if receipt.total is None:
                continue
            if abs(receipt.total - total) > TOTAL_TOLERANCE:
                continue
            if (receipt.store_name or "").strip().lower() == normalized_store:
                matches[receipt.id] = receipt

    return list(matches.values())
