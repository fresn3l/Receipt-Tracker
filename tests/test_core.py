from datetime import date

from backend.analytics import compute_product_analytics
from backend.receipt_service import needs_review, mark_receipt_reviewed, build_receipt_detail
from backend.schemas import PricePoint
from backend.validation import validate_receipt
from backend.models import LineItem, Receipt
from backend.import_service import import_json_data, IMPORTED_IMAGE_PLACEHOLDER
from backend.store_service import normalize_store_name


def test_validate_receipt_mismatch():
    items = [LineItem(raw_name="milk", quantity=1, unit_price=3.99, line_total=3.99)]
    result = validate_receipt(10.0, items)
    assert not result.is_valid
    assert result.difference == -6.01


def test_product_analytics_change():
    history = [
        PricePoint(purchase_date=date(2026, 1, 1), unit_price=3.0, line_total=None, quantity=1, receipt_id=1),
        PricePoint(purchase_date=date(2026, 2, 1), unit_price=3.3, line_total=None, quantity=1, receipt_id=2),
    ]
    analytics = compute_product_analytics(history)
    assert analytics.change_since_previous_pct == 10.0


def test_normalize_store_name():
    assert normalize_store_name("TRADER JOE'S #123") == "Trader Joe's"
    assert normalize_store_name("WALMART SUPERCENTER") == "Walmart"


def test_mark_reviewed_clears_queue_flag():
    receipt = Receipt(store_name="Test", total=10.0, image_path="x")
    receipt.line_items = [LineItem(raw_name="milk", quantity=1, line_total=3.0)]
    validation = validate_receipt(10.0, receipt.line_items)
    assert needs_review(receipt, validation, [])
    mark_receipt_reviewed(receipt)
    assert receipt.reviewed_at is not None
    assert not needs_review(receipt, validation, [])


def test_import_json_merge():
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from backend.database import Base
    from backend.models import Product, Receipt

    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    db = Session()

    payload = {
        "products": [{"id": 1, "canonical_name": "Milk", "category": "Dairy", "is_watched": True}],
        "receipts": [{
            "store_name": "Kroger",
            "purchase_date": "2026-06-01",
            "total": 4.99,
            "line_items": [{"raw_name": "Milk", "quantity": 1, "unit_price": 4.99, "line_total": 4.99, "product_id": 1}],
        }],
    }
    result = import_json_data(db, payload)
    db.commit()
    assert result["imported_receipts"] == 1
    assert db.query(Product).count() == 1
    assert db.query(Receipt).first().image_path == IMPORTED_IMAGE_PLACEHOLDER
    db.close()
