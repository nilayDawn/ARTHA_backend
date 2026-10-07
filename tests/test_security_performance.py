import io

import pytest
from fastapi.testclient import TestClient

from app.adapters.cache.memory_cache import MemoryCacheAdapter
from app.adapters.database.memory_repo import InMemoryTransactionRepository
from app.core.rate_limiter import RateLimiter
from app.core.security import get_current_user
from app.main import app
from app.modules.finance.service import TransactionService

client = TestClient(app)


def test_security_headers_present():
    res = client.get("/")
    assert res.status_code == 200
    assert res.headers.get("X-Content-Type-Options") == "nosniff"
    assert res.headers.get("X-Frame-Options") == "DENY"
    assert "Strict-Transport-Security" in res.headers


def test_input_validation_negative_amount_rejected():
    app.dependency_overrides[get_current_user] = lambda: {"id": "user_val_1", "email": "val@artha.ai"}
    try:
        # Negative amount
        res = client.post("/api/v1/transactions", json={
            "amount": -50.0,
            "category": "Food",
            "merchant": "Cafe",
            "date": "2026-03-01",
        })
        assert res.status_code == 422

        # Invalid month format
        res_budget = client.post("/api/v1/budgets", json={
            "category": "Food",
            "monthly_limit": 1000.0,
            "month": "invalid-month",
        })
        assert res_budget.status_code == 422
    finally:
        app.dependency_overrides.clear()


def test_rate_limiter_triggers_429():
    cache = MemoryCacheAdapter()
    limiter = RateLimiter(max_requests=3, window_seconds=60, by_ip=True)

    class DummyRequest:
        url = type("URL", (), {"path": "/test-limited"})()
        headers = {}
        client = type("Client", (), {"host": "192.168.1.100"})()

    req = DummyRequest()

    # 3 allowed requests
    limiter(req, cache=cache)
    limiter(req, cache=cache)
    limiter(req, cache=cache)

    # 4th request must raise 429
    with pytest.raises(Exception) as exc_info:
        limiter(req, cache=cache)
    assert exc_info.value.status_code == 429
    assert "Rate limit exceeded" in exc_info.value.detail


def test_document_upload_max_size_enforced():
    app.dependency_overrides[get_current_user] = lambda: {"id": "user_upload_1", "email": "up@artha.ai"}
    try:
        # Fake 16MB file
        oversized = io.BytesIO(b"A" * (16 * 1024 * 1024))
        res = client.post(
            "/api/v1/documents/upload",
            files={"file": ("large_file.pdf", oversized, "application/pdf")},
        )
        assert res.status_code == 413
        assert "exceeds maximum allowed limit" in res.json()["detail"]
    finally:
        app.dependency_overrides.clear()


def test_summary_caching():
    tx_repo = InMemoryTransactionRepository()
    cache = MemoryCacheAdapter()
    service = TransactionService(tx_repo=tx_repo, cache=cache)

    service.create_transaction("u_cache_1", {"amount": 500.0, "category": "Food", "merchant": "Cafe", "date": "today"})
    
    # First call: populates cache
    s1 = service.get_summary("u_cache_1")
    assert s1["total_expenses"] == 500.0

    # Modify repo directly behind the back
    tx_repo.transactions.clear()

    # Second call within TTL: served from cache
    s2 = service.get_summary("u_cache_1")
    assert s2["total_expenses"] == 500.0
