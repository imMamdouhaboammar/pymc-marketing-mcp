"""Pure ASGI native admission middleware for the MCP HTTP ingress path.

This middleware intercepts the raw ASGI request body **before** the MCP SDK parses it,
runs Rust-native `fast_admit_request()` for:
  - Payload size enforcement (≤ 10 MB, aligned with RequestSafetyMiddleware)
  - JSON-RPC framing validation
  - jsonrpc version validation ("2.0" required)
  - Method extraction
  - Request ID / correlation ID extraction
  - Notification semantics preservation
  - Malformed JSON rejection

On rejection, returns a JSON-RPC 2.0-compliant error response immediately, before any
expensive downstream Python or MCP SDK work runs.

On admission, attaches extracted metadata to `request.state`:
  - `request.state.native_request_id`  — extracted from JSON-RPC `id` field (None for notifications)
  - `request.state.native_tool_name`   — extracted from `params.name` for tools/call
  - `request.state.is_notification`    — True if no id field present
  - `request.state.native_payload_size`

# Why a raw ASGI middleware instead of BaseHTTPMiddleware?

`BaseHTTPMiddleware` buffers the entire body, which causes problems with:
  - Streaming requests
  - Very large bodies (double-buffered in Python heap)
  - Disconnect semantics

This implementation uses the low-level ASGI interface, reads the body once with a
bounded limit, calls Rust admission, then provides the exact same bytes back to the
downstream app via a memoized `receive` callable — so the body is available exactly
once downstream, without double-buffering beyond the admission limit.

# MCP SDK compatibility

The MCP Streamable HTTP transport reads the body once when handling a POST to /mcp.
Our synthetic `receive` callable yields the buffered bytes as if they just arrived.
The MCP SDK never sees the difference.

# stdio compatibility

This middleware is wired only to the HTTP app (`create_http_app`). The stdio transport
does not go through ASGI middleware and is unaffected.

# Defense-in-depth

`RequestSafetyMiddleware` runs outside this middleware and handles:
  - Rate limiting (IP-based sliding window)
  - Correlation ID attachment to HTTP response headers
  - Any non-MCP routes

The Content-Length header check in `RequestSafetyMiddleware` is retained as a
cheap pre-check for routes where body buffering would otherwise occur (artifact
downloads, control API). It provides defense-in-depth without redundant cost.
"""

from __future__ import annotations

import json
import logging
from typing import Any

logger = logging.getLogger(__name__)
_NATIVE_BOUNDARY_ERRORS = (RuntimeError, ValueError, TypeError, OSError)

MAX_ADMISSION_BODY_BYTES = 10 * 1024 * 1024  # 10 MB — must match engine.rs DEFAULT_MAX_REQUEST_SIZE


def _build_jsonrpc_error_response(
    code: str,
    message: str,
    http_status: int,
    request_id: str | int | None = None,
    error_id: str | None = None,
    actionable: bool = True,
) -> tuple[int, bytes]:
    """Build a JSON-RPC 2.0 error response body."""
    body: dict[str, Any] = {
        "jsonrpc": "2.0",
        "id": request_id,
        "error": {
            "code": (
                -32700
                if code == "MALFORMED_JSON_RPC"
                else (-32602 if code in ("INVALID_PARAMS", "INVALID_TOOL_CALL") else -32600)
            ),
            "message": message,
            "data": {
                "native_code": code,
                "error_id": error_id,
                "actionable": actionable,
            },
        },
    }
    return http_status, json.dumps(body).encode("utf-8")


class NativeAdmissionMiddleware:
    """Pure ASGI middleware that runs Rust-native request admission on the MCP hot path.

    Runs inside MCPAuthMiddleware and RequestSafetyMiddleware. Authentication remains
    the outer security boundary, while safety headers and rate limiting still apply to
    native rejections before the MCP SDK performs JSON-RPC parsing.

    Only applies Rust admission to POST requests to ``/mcp`` (the MCP endpoint).
    All other routes pass through without buffering.
    """

    def __init__(self, app, mcp_path: str = "/mcp") -> None:
        self._app = app
        self._mcp_path = mcp_path

    async def __call__(self, scope, receive, send) -> None:
        if scope["type"] != "http":
            # Pass WebSocket and lifespan events through unchanged
            await self._app(scope, receive, send)
            return

        method = scope.get("method", "")
        path = scope.get("path", "")

        # Only buffer and admit POST requests to /mcp
        # All other routes (health, artifacts, well-known) pass through
        if method != "POST" or path != self._mcp_path:
            await self._app(scope, receive, send)
            return

        # Read the body with bounded memory
        body_chunks: list[bytes] = []
        total_size = 0
        too_large = False

        while True:
            message = await receive()
            if message["type"] == "http.request":
                chunk = message.get("body", b"")
                total_size += len(chunk)
                if total_size > MAX_ADMISSION_BODY_BYTES:
                    too_large = True
                    break
                body_chunks.append(chunk)
                if not message.get("more_body", False):
                    break
            elif message["type"] == "http.disconnect":
                # Client disconnected — pass disconnect downstream
                await self._app(scope, _single_message_receive(message), send)
                return

        if too_large:
            # Reject before Rust call — body would exceed limit
            status, body = _build_jsonrpc_error_response(
                code="PAYLOAD_TOO_LARGE",
                message=f"Payload size exceeds maximum allowed {MAX_ADMISSION_BODY_BYTES} bytes",
                http_status=413,
                actionable=True,
            )
            await _send_response(send, status, body)
            return

        raw_bytes = b"".join(body_chunks)

        # Run Rust-native admission
        try:
            from marketing_mcp.accelerators import fast_admit_request

            admission = fast_admit_request(raw_bytes, MAX_ADMISSION_BODY_BYTES, tenant_id=None)
        except _NATIVE_BOUNDARY_ERRORS:
            # Fail open so the canonical MCP SDK can still handle the request.
            logger.exception("Native MCP admission failed; using canonical Python path")
            from marketing_mcp.accelerators import NATIVE_FALLBACK_COUNT_REF

            try:
                NATIVE_FALLBACK_COUNT_REF()
            except _NATIVE_BOUNDARY_ERRORS:
                logger.exception("Failed to increment native fallback counter")
            await self._app(scope, _body_replay_receive(raw_bytes, receive), send)
            return

        if not admission.get("admitted", False):
            err = admission.get("error") or {}
            code = err.get("code", "ADMISSION_FAILED")
            message = err.get("message", "Request rejected by native admission")
            error_id = err.get("error_id")
            actionable = err.get("actionable", True)

            if err.get("is_notification", False):
                await _send_response(send, 202, b"")
                return

            http_status = 413 if code == "PAYLOAD_TOO_LARGE" else 400

            status, body = _build_jsonrpc_error_response(
                code=code,
                message=message,
                http_status=http_status,
                request_id=err.get("request_id"),
                error_id=error_id,
                actionable=actionable,
            )
            await _send_response(send, status, body)
            return

        # Attach admission metadata to scope extensions for downstream use
        # (scope["state"] is available in Starlette 0.20+)
        scope.setdefault("state", {})
        scope["state"]["native_request_id"] = admission.get("request_id")
        scope["state"]["native_tool_name"] = admission.get("tool_name")
        scope["state"]["is_notification"] = admission.get("is_notification", False)
        scope["state"]["native_payload_size"] = admission.get("payload_size", len(raw_bytes))
        scope["state"]["native_method"] = admission.get("method")

        # Pass the buffered body downstream so the MCP SDK can read it
        await self._app(scope, _body_replay_receive(raw_bytes, receive), send)


def _single_message_receive(message: dict):
    """Create a receive callable that yields a single pre-read message."""
    consumed = False

    async def _receive():
        nonlocal consumed
        if not consumed:
            consumed = True
            return message
        return {"type": "http.disconnect"}

    return _receive


def _body_replay_receive(body: bytes, receive):
    """Replay the buffered body, then preserve the live ASGI receive channel.

    Streamable HTTP may keep listening for a real client disconnect while it sends
    an SSE response. Synthesizing a disconnect here closes that response before the
    MCP result is delivered.
    """
    sent = False

    async def _receive():
        nonlocal sent
        if not sent:
            sent = True
            return {
                "type": "http.request",
                "body": body,
                "more_body": False,
            }
        return await receive()

    return _receive


async def _send_response(send, status: int, body: bytes) -> None:
    """Send a simple HTTP response through the ASGI send callable."""
    await send(
        {
            "type": "http.response.start",
            "status": status,
            "headers": [
                (b"content-type", b"application/json"),
                (b"content-length", str(len(body)).encode()),
            ],
        }
    )
    await send(
        {
            "type": "http.response.body",
            "body": body,
            "more_body": False,
        }
    )
