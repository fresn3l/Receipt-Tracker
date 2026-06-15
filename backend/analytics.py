from datetime import date

from backend.schemas import PriceChange, PricePoint, ProductAnalytics


def effective_unit_price(point: PricePoint) -> float | None:
    if point.unit_price is not None:
        return point.unit_price
    if point.line_total is not None and point.quantity:
        return round(point.line_total / point.quantity, 4)
    return point.line_total


def _days_between(start: date, end: date) -> int:
    return (end - start).days


def compute_product_analytics(history: list[PricePoint]) -> ProductAnalytics:
    enriched: list[tuple[PricePoint, float]] = []
    for point in history:
        price = effective_unit_price(point)
        if price is not None:
            enriched.append((point, price))

    if not enriched:
        return ProductAnalytics(
            purchase_count=len(history),
            avg_price=None,
            min_price=None,
            max_price=None,
            latest_price=None,
            first_price=None,
            change_since_first_pct=None,
            change_since_previous_pct=None,
            avg_days_between_purchases=None,
            changes=[],
        )

    prices = [price for _, price in enriched]
    first_price = prices[0]
    latest_price = prices[-1]
    avg_price = round(sum(prices) / len(prices), 2)
    min_price = round(min(prices), 2)
    max_price = round(max(prices), 2)

    change_since_first_pct = None
    if first_price:
        change_since_first_pct = round(((latest_price - first_price) / first_price) * 100, 1)

    change_since_previous_pct = None
    if len(prices) >= 2 and prices[-2]:
        change_since_previous_pct = round(((latest_price - prices[-2]) / prices[-2]) * 100, 1)

    avg_days_between = None
    dated_points = [(point.purchase_date, price) for point, price in enriched if point.purchase_date]
    if len(dated_points) >= 2:
        gaps = [
            _days_between(dated_points[i][0], dated_points[i + 1][0])
            for i in range(len(dated_points) - 1)
        ]
        avg_days_between = round(sum(gaps) / len(gaps), 1)

    changes: list[PriceChange] = []
    for index in range(1, len(enriched)):
        prev_point, prev_price = enriched[index - 1]
        point, price = enriched[index]
        if not prev_price:
            continue
        pct = round(((price - prev_price) / prev_price) * 100, 1)
        changes.append(
            PriceChange(
                from_date=prev_point.purchase_date,
                to_date=point.purchase_date,
                from_price=round(prev_price, 2),
                to_price=round(price, 2),
                change_pct=pct,
                receipt_id=point.receipt_id,
            )
        )

    return ProductAnalytics(
        purchase_count=len(history),
        avg_price=avg_price,
        min_price=min_price,
        max_price=max_price,
        latest_price=round(latest_price, 2),
        first_price=round(first_price, 2),
        change_since_first_pct=change_since_first_pct,
        change_since_previous_pct=change_since_previous_pct,
        avg_days_between_purchases=avg_days_between,
        changes=changes,
    )
