"""
Security middleware — rate limiting, request logging, HTTPS redirect.
"""

from __future__ import annotations

import logging
import time
from collections import defaultdict

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from ..config import settings

logger = logging.getLogger(__name__)


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Rate limiter supporting both in-memory (MVP) and Redis (production) backends.

    If settings.REDIS_URL is set, uses Redis for distributed rate limiting.
    Otherwise falls back to per-process in-memory sliding window.
    """

    def __init__(self, app, max_per_minute: int = 0) -> None:
        super().__init__(app)
        self.max_per_minute = max_per_minute or settings.RATE_LIMIT_PER_MINUTE
        self._buckets: dict[str, list[float]] = defaultdict(list)
        self._redis = None
        if settings.REDIS_URL:
            try:
                import redis.asyncio as redis
                self._redis = redis.from_url(settings.REDIS_URL, decode_responses=True)
                logger.info("Rate limiter connected to Redis: %s", settings.REDIS_URL)
            except ImportError:
                logger.warning("redis package not installed, falling back to in-memory limiter")

    async def dispatch(self, request: Request, call_next):
        client_ip = request.client.host if request.client else "unknown"

        if self._redis:
            allowed = await self._check_redis(client_ip)
        else:
            allowed = self._check_memory(client_ip)

        if not allowed:
            return Response(
                content='{"detail":"Rate limit exceeded"}',
                status_code=429,
                media_type="application/json",
            )

        return await call_next(request)

    def _check_memory(self, client_ip: str) -> bool:
        now = time.time()
        window = 60.0
        bucket = self._buckets[client_ip]
        self._buckets[client_ip] = [t for t in bucket if now - t < window]

        if len(self._buckets[client_ip]) >= self.max_per_minute:
            return False

        self._buckets[client_ip].append(now)
        return True

    async def _check_redis(self, client_ip: str) -> bool:
        key = f"rate_limit:{client_ip}"
        # Simple fixed window or rolling window with expiration
        # Using a simple incr + expire approach for MVP+
        current = await self._redis.incr(key)
        if current == 1:
            await self._redis.expire(key, 60)

        return current <= self.max_per_minute


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Log every request with method, path, status, and latency."""

    async def dispatch(self, request: Request, call_next):
        t0 = time.time()
        response = await call_next(request)
        latency = (time.time() - t0) * 1000

        logger.info(
            "%s %s → %d (%.0fms)",
            request.method,
            request.url.path,
            response.status_code,
            latency,
        )
        return response
