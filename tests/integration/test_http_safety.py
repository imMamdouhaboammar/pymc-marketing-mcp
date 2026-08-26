"""Integration tests for HTTP request safety controls (Wave 4 Task 7)."""

from __future__ import annotations

import pytest
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import PlainTextResponse
from starlette.testclient import TestClient

from marketing_mcp.http.safety import RequestSafetyMiddleware


@pytest.fixture
def test_app():
    app = Starlette()

    async def endpoint(request: Request):
        return PlainTextResponse("ok")

    app.add_route("/test", endpoint, methods=["GET", "POST"])
    app.add_middleware(
        RequestSafetyMiddleware,
        max_body_bytes=1024,  # 1 KB limit for tests
        requests_per_minute=5,
    )
    return app


class TestHttpSafety:
    def test_correlation_id_propagated_or_generated(self, test_app):
        client = TestClient(test_app)
        res = client.get("/test")
        assert res.status_code == 200
        assert "x-correlation-id" in res.headers

        res_custom = client.get("/test", headers={"X-Correlation-ID": "custom-trace-123"})
        assert res_custom.status_code == 200
        assert res_custom.headers["x-correlation-id"] == "custom-trace-123"

    def test_payload_exceeding_max_body_bytes_rejected(self, test_app):
        client = TestClient(test_app)
        oversized_data = "a" * 2048
        res = client.post("/test", content=oversized_data, headers={"Content-Length": "2048"})
        assert res.status_code == 413
        data = res.json()
        assert data["error"]["code"] == "RESOURCE_LIMIT_EXCEEDED"
        assert "exceeds maximum allowed" in data["error"]["message"]

    def test_rate_limiting_enforced_when_quota_exceeded(self, test_app):
        client = TestClient(test_app)
        # Limit is 5 requests/min
        for _ in range(5):
            res = client.get("/test")
            assert res.status_code == 200

        # 6th request should be 429
        res_blocked = client.get("/test")
        assert res_blocked.status_code == 429
        data = res_blocked.json()
        assert data["error"]["code"] == "RESOURCE_LIMIT_EXCEEDED"
        assert "Rate limit exceeded" in data["error"]["message"]
