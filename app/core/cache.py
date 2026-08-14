import time
from typing import Any

# Simple thread-safe in-memory global cache storage: { key: (data, expiry_timestamp) }
_GLOBAL_CACHE: dict[str, tuple[Any, float]] = {}


def get_cached_data(key: str) -> Any | None:
    """Retrieves unexpired cached value for a key."""
    if key in _GLOBAL_CACHE:
        data, expiry = _GLOBAL_CACHE[key]
        if time.time() < expiry:
            return data
        else:
            _GLOBAL_CACHE.pop(key, None)
    return None


def set_cached_data(key: str, data: Any, ttl_seconds: int = 180):
    """Caches data with specified TTL in seconds (default: 180 seconds / 3 minutes)."""
    expiry = time.time() + ttl_seconds
    _GLOBAL_CACHE[key] = (data, expiry)


def invalidate_cache_key(key: str):
    """Deletes a specific cache key."""
    _GLOBAL_CACHE.pop(key, None)


def invalidate_user_caches(user_id: str):
    """Deletes all cache keys containing the specified user_id."""
    keys_to_delete = [k for k in list(_GLOBAL_CACHE.keys()) if user_id in k]
    for k in keys_to_delete:
        _GLOBAL_CACHE.pop(k, None)
