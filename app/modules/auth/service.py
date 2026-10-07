from typing import Any

from app.ports.cache import CachePort
from app.ports.database import UserRepositoryPort
from app.utils.logger import logger


class AuthService:
    """
    Domain service for user profile, authentication checks, and user record synchronization.
    Fixes the per-request DB bottleneck by caching synchronized user statuses.
    """

    def __init__(self, user_repo: UserRepositoryPort, cache: CachePort):
        self.user_repo = user_repo
        self.cache = cache

    def sync_user_if_needed(self, user_id: str, email: str, user_metadata: dict[str, Any] | None = None) -> dict[str, Any]:
        """
        Ensures a user record exists in the public users table.
        Cached in CachePort for 600s so subsequent authenticated requests
        do NOT incur a round-trip database query.
        """
        cache_key = f"user_synced:{user_id}"
        if self.cache.get(cache_key):
            return {"id": user_id, "synced": True}

        try:
            existing = self.user_repo.get_user_by_id(user_id)
            if not existing:
                metadata = user_metadata or {}
                full_name = metadata.get("full_name") or metadata.get("name") or (email.split("@")[0] if email else "User")
                self.user_repo.upsert_user(user_id=user_id, email=email, full_name=full_name)
                logger.info("[AuthService] Synced new user profile for UserID: %s", user_id)

            self.cache.set(cache_key, True, ttl_seconds=600) # 10 minutes
            return {"id": user_id, "synced": True}
        except Exception as e:
            logger.warning("[AuthService] User sync error: %s", e)
            return {"id": user_id, "synced": False, "error": str(e)}

    def get_user_profile(self, user_id: str) -> dict[str, Any] | None:
        cache_key = f"user_profile:{user_id}"
        cached = self.cache.get(cache_key)
        if cached is not None:
            return cached

        user = self.user_repo.get_user_by_id(user_id)
        if user:
            self.cache.set(cache_key, user, ttl_seconds=300)
        return user

    def invalidate_user_profile_cache(self, user_id: str) -> None:
        self.cache.delete(f"user_profile:{user_id}")
