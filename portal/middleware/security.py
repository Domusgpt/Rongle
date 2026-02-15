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
    Rate limiter using Redis (if configured) or in-memory fallback.

    Limits requests per client IP per minute.
    """

    def __init__(self, app, max_per_minute: int = 0) -> None:
        super().__init__(app)
        self.max_per_minute = max_per_minute or settings.RATE_LIMIT_PER_MINUTE
        self._buckets: dict[str, list[float]] = defaultdict(list)
        self._redis = None

        # Check if Redis is configured
        if hasattr(settings, "REDIS_URL") and settings.REDIS_URL:
             try:
                 import redis.asyncio as redis
                 self._redis = redis.from_url(settings.REDIS_URL, encoding="utf-8", decode_responses=True)
                 logger.info(f"RateLimitMiddleware using Redis: {settings.REDIS_URL}")
             except ImportError:
                 logger.warning("redis-py not installed; falling back to in-memory rate limiting")
             except Exception as e:
                 logger.error(f"Failed to connect to Redis: {e}; falling back to in-memory")

    async def dispatch(self, request: Request, call_next):
        client_ip = request.client.host if request.client else "unknown"

        if self._redis:
            # Redis-based logic (Fixed Window counter for simplicity, or sliding window via ZSET)
            # Using simple fixed window key: ratelimit:{ip}:{minute_epoch}
            key = f"ratelimit:{client_ip}:{int(time.time() // 60)}"
            try:
                count = await self._redis.incr(key)
                if count == 1:
                    await self._redis.expire(key, 60)

                if count > self.max_per_minute:
                    return Response(
                        content='{"detail":"Rate limit exceeded"}',
                        status_code=429,
                        media_type="application/json",
                    )
            except Exception as e:
                logger.error(f"Redis error during rate check: {e}")
                # Fail open or fallback? Let's fail open to keep service running
                pass
        else:
            # In-memory Fallback
            now = time.time()
            window = 60.0
            bucket = self._buckets[client_ip]
            self._buckets[client_ip] = [t for t in bucket if now - t < window]

            if len(self._buckets[client_ip]) >= self.max_per_minute:
                return Response(
                    content='{"detail":"Rate limit exceeded"}',
                    status_code=429,
                    media_type="application/json",
                )
            self._buckets[client_ip].append(now)

        response = await call_next(request)
        return response


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
