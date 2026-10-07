from abc import ABC, abstractmethod
from typing import Any

#abstract interface for caching (In-Memory, Redis, Memcached), when an external cache is used, the implementation of this interface will be provided by the adapter for that cache. The rest of the application will use this interface to interact with the cache without needing to know the details of the underlying cache implementation.
class CachePort(ABC):
    """Abstract interface for caching (In-Memory, Redis, Memcached)."""

    @abstractmethod
    def get(self, key: str) -> Any | None:
        """Retrieve a cached value by key."""

    @abstractmethod
    def set(self, key: str, data: Any, ttl_seconds: int = 180) -> None:
        """Store a value with a time-to-live in seconds."""

    @abstractmethod
    def delete(self, key: str) -> None:
        """Delete a single cached key."""

    @abstractmethod
    def invalidate_user(self, user_id: str, prefix: str | None = None) -> None:
        """
        Invalidate cached keys associated with a specific user.
        If prefix is supplied, only keys containing both user_id and prefix are cleared.
        """
