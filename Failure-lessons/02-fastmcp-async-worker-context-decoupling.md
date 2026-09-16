# Post-Mortem 02: FastMCP Async Worker Context Decoupling

## 1. Executive Summary & Context
After enabling anonymous HTTP binding, client tool calls to the remote MCP server endpoint (`/mcp`) began failing with `AUTH_REQUIRED: Authentication required to execute tool`, despite `AUTH_ENABLED=false` being configured in the environment.

- **Component**: `src/marketing_mcp/auth.py` and `src/marketing_mcp/cli.py` (`RequestScopedContextProvider` vs `stdio_context_provider`)
- **Severity**: High (Total Functional Failure for Remote MCP Clients)
- **Time to Detect**: During end-to-end client verification with live MCP JSON-RPC messages
- **Status**: Resolved & Verified in Production

---

## 2. Symptom & Error Signature
When an MCP client (such as Claude Desktop, Cursor, or python-mcp client) sent a `tools/call` JSON-RPC message:
```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "tools/call",
  "params": {
    "name": "register_dataset",
    "arguments": {
      "path": "/data/inbox/valid_clv.csv",
      "model_type": "clv_rfm"
    }
  }
}
```
The server responded with:
```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "error": {
    "code": -32000,
    "message": "AUTH_REQUIRED: Authentication required to execute tool 'register_dataset'"
  }
}
```
Even though `/health` reported `auth_enabled: false`.

---

## 3. Root Cause Analysis
The issue stemmed from an architectural impedance mismatch between HTTP ASGI middleware and FastMCP's internal task dispatch pipeline:

1. **Async Worker Decoupling**:
   FastMCP's `streamable_http_app` accepts HTTP POST requests containing MCP messages, immediately responds with `202 Accepted` (or streams via SSE), and enqueues the actual tool invocation onto a background `asyncio` task queue.
2. **Context Loss Across Coroutine Boundaries**:
   `RequestScopedContextProvider` relied on Python `contextvars` populated during the ASGI middleware request cycle (`MCPAuthMiddleware`). Once the ASGI request finished processing its initial response, the ASGI context was cleared. When the decoupled worker picked up the tool execution task, the request context was either empty or stale.
3. **Guard Fail-Closed**:
   Tool decorators in `marketing_mcp` verify that an `ExecutionContext` exists and holds sufficient scopes (`all_scopes()`). Because the worker found no active context, it rejected the tool execution with `AUTH_REQUIRED`.

---

## 4. Resolution & Architecture Diff
The resolution required a two-tiered fix across both the HTTP middleware and the MCP server builder:

### Tier 1: `src/marketing_mcp/cli.py`
When `auth_mgr.enabled` is `False`, default the MCP server's context provider directly to `stdio_context_provider` instead of `RequestScopedContextProvider`. The `stdio_context_provider` provides an ambient, process-safe execution context with default tenant and all administrative/data scopes:
```python
    if context_provider is not None:
        ctx_provider = context_provider
    elif not auth_mgr.enabled:
        from marketing_mcp.mcp.context import stdio_context_provider

        ctx_provider = stdio_context_provider
    else:
        ctx_provider = RequestScopedContextProvider()

    mcp = create_server(app_instance, context_provider=ctx_provider)
```

### Tier 2: `src/marketing_mcp/auth.py`
In `MCPAuthMiddleware`, when `auth_manager.enabled` is `False`, explicitly establish an anonymous `AuthContext` and set an ambient `ExecutionContext` during the request:
```python
    # If authentication is disabled, establish anonymous execution context
    if not self.auth_manager.enabled:
        auth_ctx = AuthContext(
            authenticated=True,
            client_id="anonymous",
            scopes=list(all_scopes()),
            tenant_id="default",
            auth_type="stdio",
        )
        request.state.auth = auth_ctx
        principal = Principal(
            subject=auth_ctx.client_id,
            auth_type="stdio",
            scopes=all_scopes(),
            tenant_id="default",
        )
        req_id = request.headers.get("x-request-id", secrets.token_hex(8))
        exec_ctx = ExecutionContext(
            principal=principal,
            request_id=req_id,
            transport="http",
        )
        token = set_current_execution_context(exec_ctx)
        try:
            return await call_next(request)
        finally:
            reset_current_execution_context(token)
```

---

## 5. Verification & Evidence
- **Client Execution**: Live remote MCP client executed all MCP tools (`register_dataset`, `validate_dataset`, `fit_clv_model`, `predict_expected_purchases`, `predict_probability_alive`, `read_resource`) seamlessly without authentication errors.
- **Contract Integrity**: All 45 contract tests in `tests/contract/` continue to pass, proving authenticated modes remain fully guarded.
