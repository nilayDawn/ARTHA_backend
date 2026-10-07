
from app.adapters.cache.memory_cache import MemoryCacheAdapter
from app.adapters.cache.redis_cache import RedisCacheAdapter
from app.adapters.database.memory_repo import (
    InMemoryTransactionRepository,
)


def test_memory_cache_adapter_lifecycle():
    cache = MemoryCacheAdapter()
    cache.set("key1", {"value": 100}, ttl_seconds=10)
    assert cache.get("key1") == {"value": 100}

    cache.delete("key1")
    assert cache.get("key1") is None


def test_memory_cache_user_invalidation():
    cache = MemoryCacheAdapter()
    cache.set("transactions:user123:all", [1, 2, 3], ttl_seconds=60)
    cache.set("user_profile:user123", {"name": "Test"}, ttl_seconds=60)
    cache.set("user_profile:other_user", {"name": "Other"}, ttl_seconds=60)

    cache.invalidate_user("user123")
    assert cache.get("transactions:user123:all") is None
    assert cache.get("user_profile:user123") is None
    assert cache.get("user_profile:other_user") == {"name": "Other"}


def test_redis_cache_adapter_fallback():
    # When redis_url is None or invalid, falls back gracefully to in-memory adapter
    cache = RedisCacheAdapter(redis_url=None)
    cache.set("foo", "bar", ttl_seconds=10)
    assert cache.get("foo") == "bar"
    cache.delete("foo")
    assert cache.get("foo") is None


def test_in_memory_repositories():
    tx_repo = InMemoryTransactionRepository()
    tx = tx_repo.create_transaction({
        "user_id": "u1",
        "amount": 250.0,
        "category": "Food",
        "merchant": "Cafe",
        "date": "2026-03-01",
    })
    assert tx["id"] is not None
    assert len(tx_repo.get_transactions("u1")) == 1

    tx_repo.update_transaction("u1", tx["id"], {"amount": 300.0})
    updated = tx_repo.get_transactions("u1")[0]
    assert updated["amount"] == 300.0

    tx_repo.delete_transaction("u1", tx["id"])
    assert len(tx_repo.get_transactions("u1")) == 0
