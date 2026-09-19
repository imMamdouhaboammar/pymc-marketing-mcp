"""Unit tests for Settings rate limit parsing and RequestSafetyMiddleware multi-tenant keying."""

from __future__ import annotations

import os
from unittest.mock import patch

import pytest
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import PlainTextResponse
from starlette.testclient import TestClient

from marketing_mcp.config import Settings
from marketing_mcp.http.safety import InMemoryRateLimiter, RequestSafetyMiddleware


class TestSettingsRateLimit:
    def test_settings_from_env_reads_rate_limit_per_minute(self):
        with patch.dict(os.environ, {"MARKETING_MCP_RATE_LIMIT_PER_MINUTE": "350"}):
            settings = Settings.from_env()
            assert settings.rate_limit_per_minute == 350

    def test_settings_from_env_defaults_to_120(self):
        with patch.dict(os.environ, {}, clear=True):
            settings = Settings.from_env()
            assert settings.rate_limit_per_minute == 120


class TestRequestSafetyMiddlewareKeying:
    @pytest.fixture
    def app_with_safety(self):
        app = Starlette()

        async def endpoint(request: Request):
            return PlainTextResponse("ok")

        app.add_route("/api", endpoint, methods=["GET"])
        app.add_middleware(
            RequestSafetyMiddleware,
            requests_per_minute=2,
            rate_limiter=InMemoryRateLimiter(),
        )
        return app

    def test_tenants_have_isolated_rate_limits(self, app_with_safety):
        client = TestClient(app_with_safety)

        # Tenant A sends 2 requests (reaches limit of 2)
        res1 = client.get("/api", headers={"X-Tenant-ID": "tenant_a"})
        assert res1.status_code == 200
        res2 = client.get("/api", headers={"X-Tenant-ID": "tenant_a"})
        assert res2.status_code == 200

        # Tenant A's 3rd request should be 429
        res3 = client.get("/api", headers={"X-Tenant-ID": "tenant_a"})
        assert res3.status_code == 429

        # Tenant B from the SAME client host should NOT be blocked by Tenant A's limit
        res_b1 = client.get("/api", headers={"X-Tenant-ID": "tenant_b"})
        assert res_b1.status_code == 200
        res_b2 = client.get("/api", headers={"X-Tenant-ID": "tenant_b"})
        assert res_b2.status_code == 200
        res_b3 = client.get("/api", headers={"X-Tenant-ID": "tenant_b"})
        assert res_b3.status_code == 429

    def test_bearer_tokens_have_isolated_rate_limits(self, app_with_safety):
        client = TestClient(app_with_safety)

        # Token 1 uses quota
        assert client.get("/api", headers={"Authorization": "Bearer token_alpha"}).status_code == 200
        assert client.get("/api", headers={"Authorization": "Bearer token_alpha"}).status_code == 200
        assert client.get("/api", headers={"Authorization": "Bearer token_alpha"}).status_code == 429

        # Token 2 from same host still has quota
        assert client.get("/api", headers={"Authorization": "Bearer token_beta"}).status_code == 200
