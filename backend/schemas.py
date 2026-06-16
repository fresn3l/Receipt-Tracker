from datetime import date, datetime

from pydantic import BaseModel, Field


class ParsedLineItem(BaseModel):
    name: str
    quantity: float = 1.0
    unit_price: float | None = None
    line_total: float | None = None
    category: str | None = None


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

    model_config = {"from_attributes": True}


class ReceiptDetail(BaseModel):
    id: int
    store_name: str | None
    purchase_date: date | None
    total: float | None
    image_path: str
    created_at: datetime
    line_items: list[LineItemOut]
    validation: ReceiptValidation
    possible_duplicate_ids: list[int] = Field(default_factory=list)

    model_config = {"from_attributes": True}


class ReceiptUpdate(BaseModel):
    store_name: str | None = None
    purchase_date: date | None = None
    total: float | None = None


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
    analytics: ProductAnalytics
    history: list[PricePoint]


class ProductUpdate(BaseModel):
    canonical_name: str | None = None
    category: str | None = None


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
