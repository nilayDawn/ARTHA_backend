from abc import ABC, abstractmethod
from typing import Any


class CachePort(ABC):
    """Abstract interface for caching (In-Memory, Redis, Memcached)."""

    @abstractmethod
    def get(self, key: str) -> Any | None:
        """Retrieve a cached value by key."""
        pass

    @abstractmethod
    def set(self, key: str, data: Any, ttl_seconds: int = 180) -> None:
        """Store a value with a time-to-live in seconds."""
        pass

    @abstractmethod
    def delete(self, key: str) -> None:
        """Delete a single cached key."""
        pass

    @abstractmethod
    def invalidate_user(self, user_id: str) -> None:
        """Invalidate all cached keys associated with a specific user."""
        pass
