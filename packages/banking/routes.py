"""FastAPI routes for banking domain (finance-tracker logic)."""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Any, Optional

from fastapi import APIRouter, File, Form, HTTPException, Query, UploadFile
from pydantic import BaseModel, Field

from banking import service

router = APIRouter(prefix="/api/bank", tags=["banking"])


class EditTransactionBody(BaseModel):
    description: Optional[str] = None
    amount: Optional[str] = None
    date: Optional[str] = None
    category_name: Optional[str] = None
    category_parent: Optional[str] = None
    notes: Optional[str] = None


class BulkEditBody(BaseModel):
    transaction_ids: list[str]
    category_name: Optional[str] = None
    notes: Optional[str] = None


class SplitBody(BaseModel):
    splits: list[dict[str, Any]]


class MergeBody(BaseModel):
    transaction_ids: list[str]
    keep_first: bool = True


class DeleteManyBody(BaseModel):
    transaction_ids: list[str]


class BudgetBody(BaseModel):
    category_name: str
    year: int
    month: int
    amount: str
    alert_threshold: str = "0.8"
    notes: Optional[str] = None


class RuleBody(BaseModel):
    pattern: str
    category_name: str
    parent_category: Optional[str] = None
    case_sensitive: bool = False


class TestRuleBody(BaseModel):
    pattern: str
    test_strings: list[str] = Field(default_factory=list)


@router.get("/health")
def bank_health():
    service.init_workflow()
    return {"status": "ok", "domain": "banking"}


@router.post("/import")
async def import_csv(
    file: UploadFile = File(...),
    account: Optional[str] = Form(None),
    auto_categorize: bool = Form(True),
    overwrite: bool = Form(False),
    check_duplicates: bool = Form(True),
    skip_duplicates: bool = Form(True),
):
    suffix = Path(file.filename or "upload.csv").suffix or ".csv"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(await file.read())
        tmp_path = tmp.name
    try:
        result = service.import_csv_file(
            tmp_path,
            account=account,
            auto_categorize=auto_categorize,
            overwrite=overwrite,
            check_duplicates=check_duplicates,
            skip_duplicates=skip_duplicates,
        )
    finally:
        Path(tmp_path).unlink(missing_ok=True)
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error", "Import failed"))
    return result


@router.get("/transactions")
def get_transactions(page: int = Query(1, ge=1), per_page: int = Query(50, ge=1, le=1000)):
    return service.get_transactions(page=page, per_page=per_page)


@router.get("/stats")
def get_stats():
    return service.get_overall_stats()


@router.get("/monthly-summaries")
def monthly_summaries():
    return service.get_monthly_summaries()


@router.get("/category-breakdown")
def category_breakdown():
    return service.get_category_breakdown()


@router.get("/spending-patterns")
def spending_patterns():
    return service.get_spending_patterns()


@router.post("/export")
def export_transactions():
    path = service.export_transactions()
    return {"path": path}


@router.post("/recategorize")
def recategorize(overwrite: bool = True):
    return service.recategorize_all(overwrite=overwrite)


@router.patch("/transactions/{transaction_id}")
def edit_transaction(transaction_id: str, body: EditTransactionBody):
    return service.edit_transaction(transaction_id, **body.model_dump())


@router.delete("/transactions/{transaction_id}")
def delete_transaction(transaction_id: str):
    return service.delete_transaction(transaction_id)


@router.post("/transactions/delete-many")
def delete_many(body: DeleteManyBody):
    return service.delete_transactions(body.transaction_ids)


@router.post("/transactions/{transaction_id}/split")
def split_transaction(transaction_id: str, body: SplitBody):
    return service.split_transaction(transaction_id, body.splits)


@router.post("/transactions/merge")
def merge_transactions(body: MergeBody):
    return service.merge_transactions(body.transaction_ids, body.keep_first)


@router.post("/transactions/bulk-edit")
def bulk_edit(body: BulkEditBody):
    return service.bulk_edit_transactions(
        body.transaction_ids, category_name=body.category_name, notes=body.notes
    )


@router.get("/search")
def search_transactions(
    query: Optional[str] = None,
    category: Optional[str] = None,
    account: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    amount_min: Optional[str] = None,
    amount_max: Optional[str] = None,
    transaction_type: Optional[str] = None,
    is_recurring: Optional[bool] = None,
):
    return service.search_transactions(
        query=query,
        category=category,
        account=account,
        date_from=date_from,
        date_to=date_to,
        amount_min=amount_min,
        amount_max=amount_max,
        transaction_type=transaction_type,
        is_recurring=is_recurring,
    )


@router.get("/search/filters")
def search_filters():
    return service.get_search_filters()


@router.post("/budgets")
def set_budget(body: BudgetBody):
    return service.set_budget(
        body.category_name,
        body.year,
        body.month,
        body.amount,
        alert_threshold=body.alert_threshold,
        notes=body.notes,
    )


@router.get("/budgets/status")
def budget_statuses(year: int, month: int):
    return service.get_all_budget_statuses(year, month)


@router.get("/budgets/alerts")
def budget_alerts(year: int, month: int):
    return service.get_budget_alerts(year, month)


@router.delete("/budgets")
def delete_budget(category_name: str, year: int, month: int):
    return service.delete_budget(category_name, year, month)


@router.get("/budgets/templates")
def budget_templates():
    return service.get_budget_templates()


@router.get("/recurring")
def detect_recurring(min_occurrences: int = 3):
    return service.detect_recurring_transactions(min_occurrences)


@router.post("/recurring/mark")
def mark_recurring():
    return service.mark_recurring_transactions()


@router.get("/rules")
def get_rules():
    return service.get_category_rules()


@router.post("/rules")
def add_rule(body: RuleBody):
    return service.add_category_rule(
        body.pattern,
        body.category_name,
        parent_category=body.parent_category,
        case_sensitive=body.case_sensitive,
    )


@router.delete("/rules")
def remove_rule(pattern: str, category_name: str):
    return service.remove_category_rule(pattern, category_name)


@router.post("/rules/test")
def test_rule(body: TestRuleBody):
    return service.test_category_rule(body.pattern, body.test_strings)
