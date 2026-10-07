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
