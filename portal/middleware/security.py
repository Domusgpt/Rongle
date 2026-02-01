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
    Simple in-memory sliding-window rate limiter.

    Limits requests per client IP per minute.  Suitable for MVP;
    replace with Redis-backed limiter for production.
    """

    def __init__(self, app, max_per_minute: int = 0) -> None:
        super().__init__(app)
        self.max_per_minute = max_per_minute or settings.RATE_LIMIT_PER_MINUTE
        self._buckets: dict[str, list[float]] = defaultdict(list)

    async def dispatch(self, request: Request, call_next):
        client_ip = request.client.host if request.client else "unknown"
        now = time.time()
        window = 60.0

        # Prune old entries
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
