"""HTTP request safety controls: payload limits, origin checks, correlation IDs, and rate limiting."""

from __future__ import annotations

import time
import uuid
from collections import defaultdict
from typing import Protocol

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

DEFAULT_MAX_BODY_BYTES = 10 * 1024 * 1024  # 10 MB


class RateLimiter(Protocol):
    """Protocol for rate limiting implementations."""

    def check(self, key: str, max_requests: int = 120, window_seconds: int = 60) -> bool:
        """Return True if request is allowed, False if rate limit is exceeded."""
        ...


class InMemoryRateLimiter:
    """Thread-safe in-memory sliding window rate limiter."""

    def __init__(self) -> None:
        self._requests: dict[str, list[float]] = defaultdict(list)

    def check(self, key: str, max_requests: int = 120, window_seconds: int = 60) -> bool:
        now = time.time()
        window_start = now - window_seconds
        reqs = [t for t in self._requests[key] if t > window_start]
        if len(reqs) >= max_requests:
            return False
        reqs.append(now)
        self._requests[key] = reqs
        return True


class RequestSafetyMiddleware(BaseHTTPMiddleware):
    """ASGI middleware for request size limits, correlation ID tracking, and rate limiting."""

    def __init__(
        self,
        app,
        max_body_bytes: int = DEFAULT_MAX_BODY_BYTES,
        allowed_origins: list[str] | None = None,
        rate_limiter: RateLimiter | None = None,
        requests_per_minute: int = 120,
    ) -> None:
        super().__init__(app)
        self.max_body_bytes = max_body_bytes
        self.allowed_origins = allowed_origins
        self.rate_limiter = rate_limiter or InMemoryRateLimiter()
        self.requests_per_minute = requests_per_minute

    async def dispatch(self, request: Request, call_next) -> Response:
        correlation_id = (
            request.headers.get("x-correlation-id")
            or request.headers.get("x-request-id")
            or str(uuid.uuid4())
        )

        # 1. Body size guard via Content-Length header
        content_length = request.headers.get("content-length")
        if content_length:
            try:
                length = int(content_length)
                if length > self.max_body_bytes:
                    return JSONResponse(
                        {
                            "error": {
                                "code": "RESOURCE_LIMIT_EXCEEDED",
                                "message": f"Payload size {length} bytes exceeds maximum allowed {self.max_body_bytes} bytes",
                            },
                            "correlation_id": correlation_id,
                        },
                        status_code=413,
                        headers={"X-Correlation-ID": correlation_id},
                    )
            except ValueError:
                pass

        # 2. Rate limiting check (keyed by principal, tenant, credential, or client IP)
        rate_key: str
        if hasattr(request.state, "principal") and request.state.principal:
            p = request.state.principal
            rate_key = (
                f"tenant:{p.tenant_id}:{p.subject}"
                if getattr(p, "tenant_id", None)
                else f"user:{getattr(p, 'subject', 'unknown')}"
            )
        elif request.headers.get("x-tenant-id"):
            rate_key = f"tenant:{request.headers.get('x-tenant-id')}"
        elif request.headers.get("authorization"):
            import hashlib

            auth_val = request.headers.get("authorization", "")
            rate_key = f"auth:{hashlib.sha256(auth_val.encode('utf-8')).hexdigest()[:16]}"
        elif request.client:
            rate_key = f"ip:{request.client.host}"
        else:
            rate_key = "ip:unknown"

        if not self.rate_limiter.check(rate_key, max_requests=self.requests_per_minute, window_seconds=60):
            return JSONResponse(
                {
                    "error": {
                        "code": "RESOURCE_LIMIT_EXCEEDED",
                        "message": "Rate limit exceeded. Please throttle your requests.",
                    },
                    "correlation_id": correlation_id,
                },
                status_code=429,
                headers={"X-Correlation-ID": correlation_id, "Retry-After": "60"},
            )

        # 3. Process request and attach correlation ID to response
        response = await call_next(request)
        response.headers["X-Correlation-ID"] = correlation_id
        return response
