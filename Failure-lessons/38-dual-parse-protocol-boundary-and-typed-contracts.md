# Lesson 38: Dual-Parse Protocol Boundary & Typed Contracts

### Context
Ingress validation in `NativeAdmissionMiddleware` and boundary data exchange between Rust and Python services.

### What happened
Earlier plans claimed "zero-copy AST injection" into FastMCP. In reality, the official Python MCP SDK does not allow injecting pre-parsed JSON ASTs, requiring a second parse inside the SDK. Furthermore, the typed boundary structs described in architecture docs (`InteractionRequest`/`InteractionResponse`) were missing in the codebase, leading to untyped dictionary passing across FFI.

### Observable symptom
Wire requests were parsed twice (once in Rust for admission, once in Python MCP SDK for dispatch), and data crossed between Rust and Python as untyped dictionaries without static verification.

### Impact
Hidden duplicate allocations occurred on every request, and boundary contract drift was undetected by type checkers.

### Incorrect assumption
Assumed the MCP Python SDK provided an extension point to bypass JSON parsing with an in-memory object.

### Root cause
**Confirmed**. The MCP Python SDK `StreamableHTTP` session manager is closed to external pre-parsed AST injection.

### Why the architecture allowed it
Wire admission was designed conceptually without tracing the exact SDK internal call chain.

### Fix
1. Acknowledged the dual-parse boundary truthfully in `NATIVE-INTERACTION-RUNTIME-AUDIT.md`: Rust parses for bounded-memory early rejection and size enforcement (10 MB); Python MCP SDK parses for JSON-RPC dispatch.
2. Implemented typed boundary structs in Rust (`InteractionRequest`, `InteractionResponse` in `engine.rs` with serde derives) and in Python (`BoundaryRequest`, `BoundaryResponse` in `marketing_mcp.accelerators.boundary`).
3. Added PyO3 conversion constructors `fast_create_interaction_request` and `fast_create_interaction_response`.

### Verification
- Tested by `test_typed_boundary_request_and_response` in `tests/integration/test_native_hot_path.py`.
- Unit test `test_typed_interaction_boundary_roundtrip` in Rust (`crates/marketing_mcp_fast/src/engine.rs`).

### Prevention rule
> **Do not claim zero-copy handoffs unless the receiving framework explicitly supports AST injection. Always define explicit, typed boundary contracts between languages with roundtrip serialization tests.**

### Reusable lesson
When layering security preflight ahead of a third-party framework, justify duplicate parsing solely on resource-exhaustion prevention and DoS protection, not on false claims of zero-copy speedup.

### Related code
- `src/marketing_mcp/accelerators/boundary.py`
- `crates/marketing_mcp_fast/src/engine.rs`
- `src/marketing_mcp/http/native_middleware.py`

### Related tests
- `tests/integration/test_native_hot_path.py::test_typed_boundary_request_and_response`
- `crates/marketing_mcp_fast/src/engine.rs::tests::test_typed_interaction_boundary_roundtrip`

### Related lessons
- [29-pseudonative-serialization-roundtrip-penalty.md](./29-pseudonative-serialization-roundtrip-penalty.md)
- [31-mcp-protocol-inversion-and-admission-boundary.md](./31-mcp-protocol-inversion-and-admission-boundary.md)

### Status
Resolved
