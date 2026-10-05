from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_root_and_health():
    res = client.get("/")
    assert res.status_code == 200
    assert res.json()["status"] == "online"

    health = client.get("/health")
    assert health.status_code == 200
    assert health.json()["status"] == "healthy"


def test_catalogue_endpoints():
    res = client.get("/api/v1/catalogue/categories")
    assert res.status_code == 200
    cats = res.json()
    assert len(cats) >= 5
    assert any(c["id"] == "income" for c in cats)
    assert any(c["id"] == "food" for c in cats)

    merchants = client.get("/api/v1/catalogue/merchants")
    assert merchants.status_code == 200
    assert len(merchants.json()) > 0

    templates = client.get("/api/v1/catalogue/budget-templates")
    assert templates.status_code == 200
    assert len(templates.json()) > 0


def test_payment_mock_checkout():
    # Mock authentication token header or fake user
    from app.core.security import get_current_user

    # Override get_current_user dependency for test
    app.dependency_overrides[get_current_user] = lambda: {"id": "test_user_1", "email": "test@artha.ai"}

    try:
        res = client.post("/api/v1/payments/checkout", json={
            "plan_id": "pro_monthly",
            "success_url": "https://artha.ai/dashboard?payment=success",
            "cancel_url": "https://artha.ai/dashboard?payment=cancelled",
        })
        assert res.status_code == 200
        data = res.json()
        assert "checkout_url" in data
        assert data["status"] == "ready"

        sub = client.get("/api/v1/payments/subscription")
        assert sub.status_code == 200
        assert sub.json()["user_id"] == "test_user_1"
    finally:
        app.dependency_overrides.clear()
