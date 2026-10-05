import datetime

from app.adapters.cache.memory_cache import MemoryCacheAdapter
from app.adapters.database.memory_repo import InMemoryTransactionRepository
from app.services.transaction_service import TransactionService


def test_transaction_service_date_normalization():
    tx_repo = InMemoryTransactionRepository()
    cache = MemoryCacheAdapter()
    service = TransactionService(tx_repo=tx_repo, cache=cache)

    today_str = datetime.date.today().isoformat()
    yesterday_str = (datetime.date.today() - datetime.timedelta(days=1)).isoformat()
    three_days_ago_str = (datetime.date.today() - datetime.timedelta(days=3)).isoformat()

    assert service.normalize_date("today") == today_str
    assert service.normalize_date("yesterday") == yesterday_str
    assert service.normalize_date("3 days ago") == three_days_ago_str
    assert service.normalize_date("2026-05-15") == "2026-05-15"


def test_transaction_service_auto_tag_income():
    assert TransactionService.auto_tag_income("Company Salary Deposit", "General") == "Income"
    assert TransactionService.auto_tag_income("Uber", "Transport") == "Transport"
    assert TransactionService.auto_tag_income("Freelance paycheck", "Other") == "Income"


def test_transaction_service_summary_calculation():
    tx_repo = InMemoryTransactionRepository()
    cache = MemoryCacheAdapter()
    service = TransactionService(tx_repo=tx_repo, cache=cache)

    service.create_transaction("u1", {"amount": 50000.0, "category": "Income", "merchant": "Employer", "date": "today"})
    service.create_transaction("u1", {"amount": 10000.0, "category": "Food", "merchant": "Groceries", "date": "today"})
    service.create_transaction("u1", {"amount": 5000.0, "category": "Shopping", "merchant": "Amazon", "date": "today"})

    summary = service.get_summary("u1")
    assert summary["total_income"] == 50000.0
    assert summary["total_expenses"] == 15000.0
    assert summary["savings"] == 35000.0
    assert summary["savings_rate"] == 70.0
    assert summary["count"] == 3
    assert summary["category_spending"]["Food"] == 10000.0
    assert summary["category_spending"]["Shopping"] == 5000.0
