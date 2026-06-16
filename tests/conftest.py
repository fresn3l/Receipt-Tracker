import os
import tempfile

_fd, _test_db = tempfile.mkstemp(suffix=".db")
os.close(_fd)
os.environ.setdefault("RECEIPT_TRACKER_DB", _test_db)

import pytest
from fastapi.testclient import TestClient

from backend.database import Base, engine
from backend.main import app
from backend.migrations import run_migrations

SAMPLE_IMPORT = {
    "products": [
        {"id": 1, "canonical_name": "Milk", "category": "Dairy", "is_watched": True},
        {"id": 2, "canonical_name": "Bananas", "category": "Produce"},
    ],
    "receipts": [
        {
            "store_name": "Kroger",
            "purchase_date": "2026-06-01",
            "total": 7.48,
            "line_items": [
                {
                    "raw_name": "Milk",
                    "quantity": 1,
                    "unit_price": 4.99,
                    "line_total": 4.99,
                    "product_id": 1,
                },
                {
                    "raw_name": "Bananas",
                    "quantity": 2,
                    "unit_price": 1.25,
                    "line_total": 2.49,
                    "product_id": 2,
                },
            ],
        },
        {
            "store_name": "Trader Joe's",
            "purchase_date": "2026-06-10",
            "total": 5.49,
            "line_items": [
                {
                    "raw_name": "Milk",
                    "quantity": 1,
                    "unit_price": 5.49,
                    "line_total": 5.49,
                    "product_id": 1,
                },
            ],
        },
    ],
}


@pytest.fixture(autouse=True)
def reset_db():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    run_migrations()
    yield


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def imported_client(client):
    response = client.post("/api/import/json", json={"data": SAMPLE_IMPORT, "replace": False})
    assert response.status_code == 200
    return client
