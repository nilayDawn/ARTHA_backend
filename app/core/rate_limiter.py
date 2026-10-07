import time

from fastapi import Depends, HTTPException, Request, status

from app.api.dependencies import get_cache_adapter
from app.ports.cache import CachePort
from app.utils.logger import logger


class RateLimiter:
    """
    High-performance sliding/fixed-window Rate Limiter.
    Utilizes CachePort (Redis or In-Memory fallback).
    Protects endpoints from brute-force attacks, DDoS, and LLM quota exhaustion.
    """

    def __init__(self, max_requests: int, window_seconds: int = 60, by_ip: bool = False):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.by_ip = by_ip

    def __call__(
        self,
        request: Request,
        cache: CachePort = Depends(get_cache_adapter),
    ) -> None:
        # Determine client identifier
        client_id = None
        if self.by_ip:
            forwarded = request.headers.get("X-Forwarded-For")
            if forwarded:
                client_id = forwarded.split(",")[0].strip() # Use first IP in X-Forwarded-For
            elif request.client:
                client_id = request.client.host     # else fallback to direct client IP
        else:
            # Check user token or fall back to IP
            auth_header = request.headers.get("Authorization", "")
            if auth_header.startswith("Bearer "):
                token = auth_header[7:].strip()     #slicing to remove "Bearer "
                # Hash or short slice of token to identify authenticated user
                client_id = f"user_{token[-16:]}" if len(token) >= 16 else f"user_{token}"      #slice last 16 chars
            else:
                forwarded = request.headers.get("X-Forwarded-For")
                client_id = forwarded.split(",")[0].strip() if forwarded else (request.client.host if request.client else "unknown")

        client_id = client_id or "anonymous"
        route_path = request.url.path

        # set rate limit key for the client and the specific route
        cache_key = f"rate_limit:{route_path}:{client_id}"
        record = cache.get(cache_key)

        now = time.time()
        if record is None:
            # First request in window
            cache.set(cache_key, {"count": 1, "reset_at": now + self.window_seconds}, ttl_seconds=self.window_seconds)
            return

        count = record.get("count", 0)
        reset_at = record.get("reset_at", now + self.window_seconds)
        remaining_seconds = max(1, int(reset_at - now))

        if count >= self.max_requests:
            logger.warning("[Rate Limit Exceeded] Route: %s | Client: %s | Count: %d/%d", route_path, client_id, count, self.max_requests)
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Rate limit exceeded. Maximum {self.max_requests} requests per {self.window_seconds}s. Please retry in {remaining_seconds} seconds.",
                headers={"Retry-After": str(remaining_seconds)},
            )

        # Increment count
        cache.set(cache_key, {"count": count + 1, "reset_at": reset_at}, ttl_seconds=remaining_seconds)
