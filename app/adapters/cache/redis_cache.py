import json
from typing import Any

from app.adapters.cache.memory_cache import MemoryCacheAdapter
from app.ports.cache import CachePort
from app.utils.logger import logger


class RedisCacheAdapter(CachePort):
    """
    Redis cache implementation using REDIS_URL.
    Gracefully falls back to MemoryCacheAdapter if Redis is unreachable or unconfigured.
    """

    def __init__(self, redis_url: str | None = None):
        self.redis_url = redis_url
        self._redis_client = None
        self._fallback_cache = MemoryCacheAdapter()

        if self.redis_url:
            try:
                import redis
                self._redis_client = redis.from_url(
                    self.redis_url,
                    decode_responses=True,
                    socket_connect_timeout=2.0,
                    socket_timeout=2.0,
                )
                self._redis_client.ping()
                logger.info("[CACHE] Successfully connected to Redis instance.")
            except Exception as e:
                logger.warning("[CACHE] Could not connect to Redis (%s). Falling back to in-memory cache.", e)
                self._redis_client = None
        else:
            logger.info("[CACHE] No REDIS_URL configured. Using in-memory cache adapter.")

    def get(self, key: str) -> Any | None:
        if self._redis_client:
            try:
                val = self._redis_client.get(key)
                if val is not None:
                    logger.debug("[REDIS HIT] Key: %s", key)
                    try:
                        return json.loads(val)
                    except Exception:
                        return val
                logger.debug("[REDIS MISS] Key: %s", key)
                return None
            except Exception as e:
                logger.warning("[REDIS ERROR] Fallback to memory on get(%s): %s", key, e)

        return self._fallback_cache.get(key)

    def set(self, key: str, data: Any, ttl_seconds: int = 180) -> None:
        if self._redis_client:
            try:
                val = json.dumps(data) if not isinstance(data, str) else data
                self._redis_client.setex(key, ttl_seconds, val)
                logger.debug("[REDIS SET] Key: %s (TTL: %ds)", key, ttl_seconds)
                return
            except Exception as e:
                logger.warning("[REDIS ERROR] Fallback to memory on set(%s): %s", key, e)

        self._fallback_cache.set(key, data, ttl_seconds)

    def delete(self, key: str) -> None:
        if self._redis_client:
            try:
                self._redis_client.delete(key)
                logger.debug("[REDIS DELETED] Key: %s", key)
            except Exception as e:
                logger.warning("[REDIS ERROR] on delete(%s): %s", key, e)

        self._fallback_cache.delete(key)

    def invalidate_user(self, user_id: str) -> None:
        if self._redis_client:
            try:
                # Scan for all keys containing the user_id pattern
                pattern = f"*{user_id}*"
                keys = list(self._redis_client.scan_iter(match=pattern, count=100))
                if keys:
                    self._redis_client.delete(*keys)
                    logger.info("[REDIS INVALIDATED USER] UserID: %s (%d keys cleared)", user_id, len(keys))
            except Exception as e:
                logger.warning("[REDIS ERROR] on invalidate_user(%s): %s", user_id, e)

        self._fallback_cache.invalidate_user(user_id)
