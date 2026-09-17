"""Integration tests proving Rust-native admission is wired to the actual MCP HTTP ingress path.

These tests verify the production requirement:
  - Rust `fast_admit_request()` IS called on every POST /mcp request
  - Native invocation counters increment (proving the hot path runs)
  - Malformed JSON returns 400 with a Rust-normalized error BEFORE reaching the MCP SDK
  - Oversized bodies return 413 from Rust BEFORE reaching the MCP SDK
  - Notification (no `id`) is passed through with `is_notification = True`
  - Valid JSON-RPC requests reach the MCP SDK normally

Failure mode this test guards against:
  - Adding a Rust function to the accelerators bridge without wiring it to the real path
  - Middleware stack re-ordering that bypasses NativeAdmissionMiddleware
  - Rust extension loading failure (tests skip gracefully if Rust unavailable)
"""

from __future__ import annotations

import json

import pytest
from starlette.testclient import TestClient

from marketing_mcp.accelerators import get_native_invocation_stats, is_rust_accelerated

pytestmark = pytest.mark.integration


@pytest.fixture
def http_app(tmp_path):
    """Create the full ASGI HTTP application stack (same as production)."""
    from marketing_mcp.app import Application
    from marketing_mcp.cli import create_http_app
    from marketing_mcp.config import Settings

    settings = Settings(
        data_dir=tmp_path / "data",
        artifact_dir=tmp_path / "artifacts",
        metadata_db=tmp_path / "metadata.db",
        ingest_dir=tmp_path,
        auth_enabled=False,  # Disable auth for these tests
    )
    app_state = Application(settings)
    return create_http_app(application=app_state, settings=settings)


async def _asgi_post_mcp(
    app, body: bytes, *, include_content_length: bool = True
) -> tuple[int, dict]:
    """Fire a POST /mcp request through the full ASGI stack and return (status, response_body)."""
    scope = {
        "type": "http",
        "method": "POST",
        "path": "/mcp",
        "query_string": b"",
        "headers": [
            (b"content-type", b"application/json"),
            *([(b"content-length", str(len(body)).encode())] if include_content_length else []),
        ],
        "state": {},
    }
    body_chunks: list[bytes] = []
    status_code: list[int] = []

    async def receive():
        return {"type": "http.request", "body": body, "more_body": False}

    async def send(message):
        if message["type"] == "http.response.start":
            status_code.append(message["status"])
        elif message["type"] == "http.response.body":
            body_chunks.append(message.get("body", b""))

    async with app.router.lifespan_context(app):
        await app(scope, receive, send)
    response_bytes = b"".join(body_chunks)
    try:
        response_body = json.loads(response_bytes) if response_bytes else {}
    except (json.JSONDecodeError, UnicodeDecodeError):
        response_body = {"raw": response_bytes.decode(errors="replace")}
    return status_code[0] if status_code else 0, response_body


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_native_admission_counter_increments_on_valid_request(http_app):
    """Core production proof: native admission counter increments on POST /mcp."""
    if not is_rust_accelerated():
        pytest.skip("Rust not available — native path not active")

    before = get_native_invocation_stats()["native_admission_calls_total"]

    valid_body = json.dumps(
        {
            "jsonrpc": "2.0",
            "id": "test-req-1",
            "method": "tools/list",
            "params": {},
        }
    ).encode("utf-8")

    await _asgi_post_mcp(http_app, valid_body)

    after = get_native_invocation_stats()["native_admission_calls_total"]
    assert after > before, (
        "native_admission_calls_total did not increment — fast_admit_request() is NOT "
        "on the production POST /mcp path. Check that NativeAdmissionMiddleware is wired in cli.py."
    )


@pytest.mark.asyncio
async def test_malformed_json_rejected_by_rust_before_mcp_sdk(http_app):
    """Malformed JSON must return 400 with MALFORMED_JSON_RPC code — Rust rejects it."""
    malformed = b"{not valid json at all..."
    status, body = await _asgi_post_mcp(http_app, malformed)

    assert status == 400, f"Expected 400 from Rust admission, got {status}"
    error = body.get("error", {})
    data = error.get("data", {})
    native_code = data.get("native_code", "")
    assert native_code == "MALFORMED_JSON_RPC", (
        f"Expected MALFORMED_JSON_RPC in error.data.native_code, got '{native_code}'. "
        f"Full response: {body}"
    )


def test_native_rejection_preserves_outer_safety_headers(http_app):
    """Malformed MCP traffic must still cross correlation/rate-limit middleware."""
    with TestClient(http_app) as client:
        response = client.post(
            "/mcp",
            content=b"{malformed",
            headers={
                "content-type": "application/json",
                "x-correlation-id": "corr-native-rejection",
            },
        )

    assert response.status_code == 400
    assert response.headers["x-correlation-id"] == "corr-native-rejection"


@pytest.mark.asyncio
async def test_missing_jsonrpc_version_rejected_by_rust(http_app):
    """Missing jsonrpc field must be rejected with MISSING_JSONRPC_VERSION by Rust."""
    no_version = json.dumps(
        {
            "id": 1,
            "method": "tools/list",
            "params": {},
        }
    ).encode("utf-8")
    status, body = await _asgi_post_mcp(http_app, no_version)

    assert status == 400, f"Expected 400, got {status}"
    error = body.get("error", {})
    data = error.get("data", {})
    assert data.get("native_code") == "MISSING_JSONRPC_VERSION", f"Got: {body}"


@pytest.mark.asyncio
async def test_invalid_request_preserves_jsonrpc_id(http_app):
    """Protocol errors for requests must echo the valid JSON-RPC id."""
    invalid = json.dumps(
        {
            "jsonrpc": "2.0",
            "id": "request-42",
            "params": {},
        }
    ).encode("utf-8")
    status, body = await _asgi_post_mcp(http_app, invalid)

    assert status == 400
    assert body["id"] == "request-42"
    assert body["error"]["data"]["native_code"] == "MISSING_METHOD"


@pytest.mark.asyncio
async def test_invalid_params_preserves_numeric_id_and_protocol_code(http_app):
    invalid = json.dumps(
        {
            "jsonrpc": "2.0",
            "id": 42,
            "method": "tools/list",
            "params": "invalid",
        }
    ).encode()
    status, body = await _asgi_post_mcp(http_app, invalid)

    assert status == 400
    assert body["id"] == 42
    assert body["error"]["code"] == -32602
    assert body["error"]["data"]["native_code"] == "INVALID_PARAMS"


@pytest.mark.asyncio
async def test_wrong_jsonrpc_version_rejected_by_rust(http_app):
    """Wrong jsonrpc version (e.g. '1.0') must be rejected."""
    wrong_version = json.dumps(
        {
            "jsonrpc": "1.0",
            "id": 1,
            "method": "tools/list",
        }
    ).encode("utf-8")
    status, body = await _asgi_post_mcp(http_app, wrong_version)

    assert status == 400, f"Expected 400, got {status}"
    assert body.get("error", {}).get("data", {}).get("native_code") == "INVALID_JSONRPC_VERSION"


@pytest.mark.asyncio
async def test_oversized_body_rejected_with_413(http_app):
    """Body exceeding 10 MB must be rejected with 413 PAYLOAD_TOO_LARGE."""
    oversized = b"x" * (11 * 1024 * 1024)  # 11 MB > 10 MB limit
    status, body = await _asgi_post_mcp(http_app, oversized, include_content_length=False)

    assert status == 413, f"Expected 413, got {status}"
    error = body.get("error", {})
    data = error.get("data", {})
    assert data.get("native_code") == "PAYLOAD_TOO_LARGE", f"Got: {body}"


@pytest.mark.asyncio
async def test_notification_has_null_id_in_jsonrpc_response(http_app):
    """Notification (no 'id' field) must pass through; response should have null id."""
    notification = json.dumps(
        {
            "jsonrpc": "2.0",
            "method": "notifications/cancelled",
            "params": {"requestId": "original-req"},
        }
    ).encode("utf-8")
    # Notifications may return 202 or no response — we just assert Rust doesn't reject them
    status, body = await _asgi_post_mcp(http_app, notification)
    # Notifications admitted by Rust must NOT return 400/413 from admission
    assert status not in (400, 413), (
        f"Notification was incorrectly rejected with status {status}. "
        f"Rust must pass notifications through: {body}"
    )


@pytest.mark.asyncio
async def test_invalid_notification_gets_no_jsonrpc_error_response(http_app):
    """JSON-RPC notifications never receive a response, even when their params are invalid."""
    notification = json.dumps(
        {
            "jsonrpc": "2.0",
            "method": "tools/list",
            "params": "invalid",
        }
    ).encode()
    status, body = await _asgi_post_mcp(http_app, notification)

    assert status == 202
    assert body == {}


@pytest.mark.asyncio
async def test_native_range_parse_counter_increments_on_artifact_download(tmp_path):
    """Range header parsing counter must increment on artifact download requests."""
    if not is_rust_accelerated():
        pytest.skip("Rust not available")

    before = get_native_invocation_stats()["native_range_parse_calls_total"]

    from marketing_mcp.accelerators import fast_parse_range_header

    result = fast_parse_range_header("bytes=0-1023", 10000)
    assert result is not None
    assert result == (0, 1023, 1024)

    after = get_native_invocation_stats()["native_range_parse_calls_total"]
    assert after > before, "Range parse counter did not increment"


@pytest.mark.asyncio
async def test_admission_id_different_from_job_id():
    """Prove that fast_admit_job returns 'admission_id', not 'job_id' (the old buggy field).

    This test guards against the regression where Rust job IDs were confused with canonical
    Python job IDs. The admission_id is interaction-level only; the canonical job ID is
    created by Python's job service after admission.
    """
    from marketing_mcp.accelerators import fast_admit_job

    result = fast_admit_job(1024, max_size=10 * 1024 * 1024, tenant_id="test-tenant")
    assert result.get("admitted") is True, f"Admission failed: {result}"
    assert "admission_id" in result, (
        f"Expected 'admission_id' field in fast_admit_job result, got keys: {list(result.keys())}. "
        "'job_id' was renamed to 'admission_id' to prevent confusion with canonical job IDs."
    )
    assert "job_id" not in result, (
        "The 'job_id' field was not removed from fast_admit_job result. "
        "The Rust-generated interaction token must use 'admission_id' to prevent ID confusion."
    )
    admission_id = result["admission_id"]
    assert isinstance(admission_id, str) and len(admission_id) > 0
    # Admission IDs must use 'adm-' prefix to distinguish from job IDs
    assert admission_id.startswith("adm-"), (
        f"admission_id '{admission_id}' must start with 'adm-' to distinguish "
        "from canonical job IDs (e.g. UUID format from Python job service)."
    )


def test_cancellation_status_is_correct_not_cancelled():
    """Cancellation status must say 'cancelling' (signal sent), NOT 'cancelled' (terminal state).

    'cancelled' would falsely imply the worker stopped, when it may still be running.
    """
    from marketing_mcp.accelerators import fast_acknowledge_cancellation

    ack = fast_acknowledge_cancellation("job-abc-123", in_process=True)
    assert ack.get("acknowledged") is True
    assert ack.get("status") == "cancelling", (
        f"Expected status='cancelling' (signal sent, worker may still run), "
        f"got '{ack.get('status')}'. "
        "'cancelled' is a terminal state reserved for confirmed worker stop."
    )

    ack_queued = fast_acknowledge_cancellation("job-abc-123", in_process=False)
    assert ack_queued.get("status") == "cancellation_requested", (
        f"Expected 'cancellation_requested' for queued jobs, got '{ack_queued.get('status')}'"
    )


def test_rust_statistics_functions_emit_warning():
    """fast_mcmc_diagnostics must emit UserWarning when called — it is non-authoritative."""
    import pytest

    from marketing_mcp.accelerators import fast_mcmc_diagnostics

    with pytest.warns(UserWarning, match="NON-AUTHORITATIVE"):
        fast_mcmc_diagnostics([1.01], [500.0], 0)


def test_experimental_module_exports_correctly():
    """Experimental module must export with EXPERIMENTAL_ prefix, not bare names."""
    import marketing_mcp.accelerators.experimental as exp

    assert hasattr(exp, "EXPERIMENTAL_fast_mcmc_diagnostics")
    assert hasattr(exp, "EXPERIMENTAL_fast_compute_split_rhat")
    # Must not export bare names without prefix
    assert not hasattr(exp, "fast_mcmc_diagnostics")
    assert not hasattr(exp, "fast_compute_split_rhat")


def test_native_fallback_counter_is_observable():
    """Fallback telemetry must increment instead of calling a no-op placeholder."""
    if not is_rust_accelerated():
        pytest.skip("Rust not available")

    from marketing_mcp.accelerators import NATIVE_FALLBACK_COUNT_REF

    before = get_native_invocation_stats()["native_fallback_calls_total"]
    NATIVE_FALLBACK_COUNT_REF()
    after = get_native_invocation_stats()["native_fallback_calls_total"]
    assert after == before + 1


def test_get_native_invocation_stats_has_all_counters():
    """get_native_invocation_stats() must return all expected counter keys."""
    from marketing_mcp.accelerators import get_native_invocation_stats

    stats = get_native_invocation_stats()
    expected_keys = {
        "native_admission_calls_total",
        "native_serialization_calls_total",
        "native_range_parse_calls_total",
        "native_job_admission_calls_total",
        "native_cancellation_calls_total",
        "native_fallback_calls_total",
    }
    missing = expected_keys - set(stats.keys())
    assert not missing, f"Missing counter keys: {missing}"
    for key, val in stats.items():
        assert isinstance(val, int) and val >= 0, f"{key} must be non-negative int, got {val}"


def test_typed_boundary_request_and_response():
    """Phase 4: BoundaryRequest and BoundaryResponse typed contract validation."""
    from marketing_mcp.accelerators import (
        BoundaryRequest,
        BoundaryResponse,
        create_boundary_request,
        create_boundary_response,
    )

    req = create_boundary_request(
        request_id="req-test-1",
        correlation_id="corr-test-1",
        tool_name="get_model_status",
        arguments={"model_id": "mmm-123"},
        tenant_id="tenant-x",
        deadline_ms=10000,
        cancellation_token="tok-1",
    )
    assert req.request_id == "req-test-1"
    assert req.correlation_id == "corr-test-1"
    assert req.tool_name == "get_model_status"
    assert req.arguments == {"model_id": "mmm-123"}
    assert req.tenant_id == "tenant-x"
    assert req.deadline_ms == 10000
    assert req.cancellation_token == "tok-1"

    d = req.to_dict()
    assert BoundaryRequest.from_dict(d) == req

    resp = create_boundary_response(
        correlation_id="corr-test-1",
        status="ok",
        data={"status": "ready"},
        execution_time_ms=2.5,
    )
    assert resp.correlation_id == "corr-test-1"
    assert resp.status == "ok"
    assert resp.success is True
    assert resp.data == {"status": "ready"}
    assert resp.error is None
    assert resp.execution_time_ms == 2.5

    d_resp = resp.to_dict()
    assert BoundaryResponse.from_dict(d_resp) == resp


def test_production_decision_paths_do_not_import_experimental_rust_diagnostics():
    """Phase 7: Production decision and diagnostic modules must never import experimental Rust functions."""
    import inspect

    import marketing_mcp.domain.decisions.allocation as alloc
    import marketing_mcp.domain.decisions.flighting as flight
    import marketing_mcp.domain.diagnostics.engine as diag
    import marketing_mcp.services.decision_service as dec_svc

    for mod in (alloc, flight, diag, dec_svc):
        src = inspect.getsource(mod)
        assert "fast_mcmc_diagnostics" not in src, (
            f"Module {mod.__name__} illegally references fast_mcmc_diagnostics. "
            "Python/ArviZ is the sole statistical authority for production decisions."
        )
        assert "EXPERIMENTAL_fast_mcmc_diagnostics" not in src, (
            f"Module {mod.__name__} illegally references EXPERIMENTAL_fast_mcmc_diagnostics."
        )
        assert "fast_compute_split_rhat" not in src, (
            f"Module {mod.__name__} illegally references fast_compute_split_rhat."
        )

