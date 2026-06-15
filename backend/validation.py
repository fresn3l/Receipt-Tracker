from backend.models import LineItem
from backend.schemas import ReceiptValidation

TOLERANCE_ABSOLUTE = 0.10
TOLERANCE_PERCENT = 0.02


def _items_sum(line_items: list[LineItem]) -> float | None:
    totals = [item.line_total for item in line_items if item.line_total is not None]
    if not totals:
        return None
    return round(sum(totals), 2)


def validate_receipt(total: float | None, line_items: list[LineItem]) -> ReceiptValidation:
    items_sum = _items_sum(line_items)
    warnings: list[str] = []
    is_valid = True

    if not line_items:
        warnings.append("No line items on this receipt.")
        is_valid = False

    difference: float | None = None
    if total is not None and items_sum is not None:
        difference = round(items_sum - total, 2)
        tolerance = max(TOLERANCE_ABSOLUTE, abs(total) * TOLERANCE_PERCENT)
        if abs(difference) > tolerance:
            warnings.append(
                f"Line items sum to ${items_sum:.2f} but receipt total is ${total:.2f} "
                f"(off by ${abs(difference):.2f})."
            )
            is_valid = False
    elif total is None and line_items:
        warnings.append("Receipt total is missing; cannot verify line items.")
    elif total is not None and items_sum is None and line_items:
        warnings.append("Line item totals are missing; cannot verify against receipt total.")
        is_valid = False

    return ReceiptValidation(
        items_sum=items_sum,
        receipt_total=total,
        difference=difference,
        is_valid=is_valid,
        warnings=warnings,
    )
