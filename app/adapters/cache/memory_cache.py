import time
from typing import Any

from app.ports.cache import CachePort
from app.utils.logger import logger


class MemoryCacheAdapter(CachePort):
    """Thread-safe in-memory TTL cache implementation."""

    def __init__(self):
        self._cache: dict[str, tuple[Any, float]] = {}

    def get(self, key: str) -> Any | None:
        if key in self._cache:
            data, expiry = self._cache[key]
            if time.time() < expiry:
                logger.debug("[CACHE HIT] Key: %s", key)
                return data
            else:
                logger.debug("[CACHE EXPIRED] Key: %s", key)
                self._cache.pop(key, None)
        logger.debug("[CACHE MISS] Key: %s", key)
        return None

    def set(self, key: str, data: Any, ttl_seconds: int = 180) -> None:
        expiry = time.time() + ttl_seconds
        self._cache[key] = (data, expiry)
        logger.debug("[CACHE SET] Key: %s (TTL: %ds)", key, ttl_seconds)

    def delete(self, key: str) -> None:
        if self._cache.pop(key, None) is not None:
            logger.debug("[CACHE DELETED] Key: %s", key)

    def invalidate_user(self, user_id: str) -> None:
        keys_to_delete = [k for k in list(self._cache.keys()) if user_id in k]
        for k in keys_to_delete:
            self._cache.pop(k, None)
        if keys_to_delete:
            logger.info("[CACHE INVALIDATED USER] UserID: %s (%d keys cleared)", user_id, len(keys_to_delete))
