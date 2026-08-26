def test_shell_index(client):
    response = client.get("/")
    assert response.status_code == 200
    assert b"Finance" in response.content
    assert b"Dashboard" in response.content


def test_bank_health(client):
    response = client.get("/api/bank/health")
    assert response.status_code == 200
    assert response.json()["domain"] == "banking"


def test_bank_stats_empty(client):
    response = client.get("/api/bank/stats")
    assert response.status_code == 200
    body = response.json()
    assert "total_income" in body


def test_app_settings(client):
    get = client.get("/api/app/settings")
    assert get.status_code == 200
    assert "data_dir" in get.json()

    patch = client.patch("/api/app/settings", json={"openai_model": "gpt-4o-mini"})
    assert patch.status_code == 200
    assert patch.json()["ok"] is True


def test_dashboard(client):
    response = client.get("/api/app/dashboard")
    assert response.status_code == 200
    body = response.json()
    assert "banking" in body
    assert "grocery" in body


def test_banking_ui(client):
    response = client.get("/banking/")
    assert response.status_code == 200
    assert b"Finance Tracker" in response.content or b"api.js" in response.content


def test_receipts_ui(client):
    response = client.get("/receipts/")
    assert response.status_code == 200
    assert b"Receipt Tracker" in response.content
