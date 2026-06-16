from datetime import date, datetime

from pydantic import BaseModel, Field


class ParsedLineItem(BaseModel):
    name: str
    quantity: float = 1.0
    unit_price: float | None = None
    line_total: float | None = None
    category: str | None = None
    unit_label: str | None = None
    unit_amount: float | None = None
    normalized_unit: str | None = None
    confidence: float | None = None


class ParsedReceipt(BaseModel):
    store_name: str | None = None
    purchase_date: date | None = None
    total: float | None = None
    line_items: list[ParsedLineItem] = Field(default_factory=list)


class LineItemOut(BaseModel):
    id: int
    raw_name: str
    quantity: float
    unit_price: float | None
    line_total: float | None
    product_id: int | None
    unit_label: str | None = None
    parse_confidence: float | None = None

    model_config = {"from_attributes": True}


class ReceiptValidation(BaseModel):
    items_sum: float | None
    receipt_total: float | None
    difference: float | None
    is_valid: bool
    warnings: list[str] = Field(default_factory=list)


class ReceiptSummary(BaseModel):
    id: int
    store_name: str | None
    purchase_date: date | None
    total: float | None
    created_at: datetime
    item_count: int
    has_warning: bool
    possible_duplicate: bool = False
    needs_review: bool = False

    model_config = {"from_attributes": True}


class ReceiptDetail(BaseModel):
    id: int
    store_name: str | None
    purchase_date: date | None
    total: float | None
    image_path: str
    created_at: datetime
    notes: str | None = None
    parse_confidence: float | None = None
    line_items: list[LineItemOut]
    validation: ReceiptValidation
    possible_duplicate_ids: list[int] = Field(default_factory=list)
    needs_review: bool = False

    model_config = {"from_attributes": True}


class ReceiptUpdate(BaseModel):
    store_name: str | None = None
    purchase_date: date | None = None
    total: float | None = None
    notes: str | None = None


class LineItemCreate(BaseModel):
    raw_name: str
    quantity: float = 1.0
    unit_price: float | None = None
    line_total: float | None = None


class LineItemUpdate(BaseModel):
    raw_name: str | None = None
    quantity: float | None = None
    unit_price: float | None = None
    line_total: float | None = None


class ProductOut(BaseModel):
    id: int
    canonical_name: str
    category: str | None
    purchase_count: int
    avg_price: float | None
    latest_price: float | None = None
    change_since_previous_pct: float | None = None
    is_watched: bool = False
    normalized_unit_price: float | None = None
    normalized_unit: str | None = None

    model_config = {"from_attributes": True}


class PricePoint(BaseModel):
    purchase_date: date | None
    unit_price: float | None
    line_total: float | None
    quantity: float
    receipt_id: int
    effective_price: float | None = None


class PriceChange(BaseModel):
    from_date: date | None
    to_date: date | None
    from_price: float
    to_price: float
    change_pct: float
    receipt_id: int


class ProductAnalytics(BaseModel):
    purchase_count: int
    avg_price: float | None
    min_price: float | None
    max_price: float | None
    latest_price: float | None
    first_price: float | None
    change_since_first_pct: float | None
    change_since_previous_pct: float | None
    avg_days_between_purchases: float | None
    changes: list[PriceChange] = Field(default_factory=list)


class ProductDetail(BaseModel):
    id: int
    canonical_name: str
    category: str | None
    aliases: list[str] = Field(default_factory=list)
    is_watched: bool = False
    normalized_unit: str | None = None
    unit_amount: float | None = None
    normalized_unit_price: float | None = None
    analytics: ProductAnalytics
    history: list[PricePoint]
    store_comparison: list["StorePriceComparison"] = Field(default_factory=list)


class ProductUpdate(BaseModel):
    canonical_name: str | None = None
    category: str | None = None
    is_watched: bool | None = None
    normalized_unit: str | None = None
    unit_amount: float | None = None


class ProductMergeRequest(BaseModel):
    target_id: int
    source_ids: list[int]


class MergeSuggestion(BaseModel):
    product_ids: list[int]
    names: list[str]
    score: float
    reason: str


class CategorySpend(BaseModel):
    category: str
    total: float


class StoreSpend(BaseModel):
    store: str
    total: float
    trip_count: int


class MonthlySpend(BaseModel):
    month: str
    total: float
    trip_count: int


class SpendingSummary(BaseModel):
    receipt_count: int
    total_spent: float
    avg_trip_total: float | None
    avg_items_per_trip: float | None


class SpendingOverview(BaseModel):
    summary: SpendingSummary
    by_category: list[CategorySpend]
    by_store: list[StoreSpend]
    monthly: list[MonthlySpend]
    monthly_budget: float | None = None
    current_month_spend: float | None = None
    budget_remaining: float | None = None


class PriceAlert(BaseModel):
    product_id: int
    product_name: str
    alert_type: str
    message: str
    latest_price: float | None
    change_pct: float | None


class StorePriceComparison(BaseModel):
    store: str
    purchase_count: int
    avg_price: float
    latest_price: float


class InflationBasket(BaseModel):
    basket_change_pct: float | None
    product_count: int


class BudgetSettings(BaseModel):
    monthly_budget: float | None
    category_budgets: dict[str, float] = Field(default_factory=dict)


class BudgetSettingsUpdate(BaseModel):
    monthly_budget: float | None = None
    category_budgets: dict[str, float] | None = None


class BatchUploadResult(BaseModel):
    saved: list[ReceiptDetail]
    failed: list[dict]
