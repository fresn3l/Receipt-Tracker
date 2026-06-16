from datetime import date

from backend.analytics import compute_product_analytics
from backend.schemas import PricePoint
from backend.validation import validate_receipt
from backend.models import LineItem


def test_validate_receipt_mismatch():
    items = [
        LineItem(raw_name="milk", quantity=1, unit_price=3.99, line_total=3.99),
    ]
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
    from backend.store_service import normalize_store_name

    assert normalize_store_name("TRADER JOE'S #123") == "Trader Joe's"
    assert normalize_store_name("WALMART SUPERCENTER") == "Walmart"
