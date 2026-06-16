from tests.conftest import SAMPLE_IMPORT


def test_health(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert "openai_api_key_configured" in body


def test_import_json(client):
    response = client.post("/api/import/json", json={"data": SAMPLE_IMPORT})
    assert response.status_code == 200
    body = response.json()
    assert body["imported_receipts"] == 2
    assert body["imported_items"] == 3
    assert body["imported_products"] == 2


def test_list_receipts(imported_client):
    response = imported_client.get("/api/receipts")
    assert response.status_code == 200
    receipts = response.json()
    assert len(receipts) == 2
    assert receipts[0]["store_name"] in ("Kroger", "Trader Joe's")


def test_get_receipt_detail(imported_client):
    listing = imported_client.get("/api/receipts").json()
    receipt_id = listing[0]["id"]
    response = imported_client.get(f"/api/receipts/{receipt_id}")
    assert response.status_code == 200
    detail = response.json()
    assert detail["id"] == receipt_id
    assert len(detail["line_items"]) >= 1


def test_mark_reviewed(imported_client):
    receipt_id = imported_client.get("/api/receipts").json()[0]["id"]
    response = imported_client.post(f"/api/receipts/{receipt_id}/mark-reviewed")
    assert response.status_code == 200
    assert response.json()["reviewed_at"] is not None
    assert response.json()["needs_review"] is False


def test_list_products(imported_client):
    response = imported_client.get("/api/products")
    assert response.status_code == 200
    products = response.json()
    names = {p["canonical_name"] for p in products}
    assert "Milk" in names
    assert "Bananas" in names


def test_watchlist(imported_client):
    response = imported_client.get("/api/products/watchlist")
    assert response.status_code == 200
    watched = response.json()
    assert len(watched) == 1
    assert watched[0]["canonical_name"] == "Milk"
    assert watched[0]["is_watched"] is True


def test_product_categories(client):
    response = client.get("/api/products/categories")
    assert response.status_code == 200
    categories = response.json()
    assert "Dairy" in categories
    assert "Produce" in categories


def test_spending_overview(imported_client):
    response = imported_client.get("/api/spending/overview")
    assert response.status_code == 200
    overview = response.json()
    assert overview["summary"]["receipt_count"] == 2
    assert len(overview["by_category"]) >= 1
    assert len(overview["monthly"]) >= 1


def test_budget_settings(imported_client):
    patch = imported_client.patch("/api/settings/budget", json={"monthly_budget": 500.0})
    assert patch.status_code == 200
    assert patch.json()["monthly_budget"] == 500.0

    get = imported_client.get("/api/settings/budget")
    assert get.status_code == 200
    assert get.json()["monthly_budget"] == 500.0


def test_export_import_roundtrip(imported_client):
    exported = imported_client.get("/api/export/json").json()
    assert len(exported["receipts"]) == 2
    assert len(exported["products"]) >= 2

    imported_client.delete("/api/receipts/1")
    imported_client.delete("/api/receipts/2")

    response = imported_client.post(
        "/api/import/json",
        json={"data": exported, "replace": True},
    )
    assert response.status_code == 200
    assert response.json()["imported_receipts"] == 2

    receipts = imported_client.get("/api/receipts").json()
    assert len(receipts) == 2


def test_export_csv(imported_client):
    response = imported_client.get("/api/export/csv")
    assert response.status_code == 200
    assert "text/csv" in response.headers["content-type"]
    assert "Milk" in response.text


def test_inflation_basket(imported_client):
    response = imported_client.get("/api/insights/inflation-basket")
    assert response.status_code == 200
    basket = response.json()
    assert "basket_change_pct" in basket


def test_delete_receipt(imported_client):
    receipt_id = imported_client.get("/api/receipts").json()[0]["id"]
    response = imported_client.delete(f"/api/receipts/{receipt_id}")
    assert response.status_code == 200
    assert response.json()["ok"] is True

    remaining = imported_client.get("/api/receipts").json()
    assert len(remaining) == 1
