# Lesson 35: Fictional Cryptographic Acceleration & Artifact Streaming Claims

### Context
Artifact delivery, HTTP Partial Content (206) streaming, and cryptographic integrity verification in `src/marketing_mcp/http/artifacts.py`, `src/marketing_mcp/storage/artifacts.py`, and `docs/architecture/rust-mcp-interaction-engine.md`.

### What happened
Architectural documentation asserted that Rust provided "SIMD SHA-256 Checksums" and "zero-copy native chunked artifact streaming with bounded backpressure buffers". Code audit revealed that neither SIMD hashing nor native streaming existed in the codebase. Range header parsing was implemented in Rust (`fast_parse_range_header`), but file chunking and streaming was handled entirely by Python ASGI `StreamingResponse` using standard `hashlib.sha256`.

### Observable symptom
In documentation audits, claims of SIMD speedup could not be reproduced or located in `crates/marketing_mcp_fast`. `Cargo.toml` lacked any cryptographic crate dependency (such as `sha2` with asm features), and no native stream buffer loop existed.

### Impact
Deceptive architectural claims misled performance expectations, caused confusion during runtime verification, and obscured where system bottlenecks actually lay.

### Incorrect assumption
Assumed that an aspirational target architecture specification represented deployed, active production code.

### Root cause
**Confirmed**. The initial architecture document drafted target-state specifications before implementation and prematurely marked unbuilt capabilities as part of the production engine.

### Why the architecture allowed it
Documentation was decoupled from runtime invocation counters and CI assertion gates, permitting claims to survive without traceable code evidence.

### Fix
Reconciled documentation to reflect runtime truth:
1. Marked SIMD SHA-256 as `REMOVE_CLAIM` in `docs/NATIVE-INTERACTION-RUNTIME-AUDIT.md`.
2. Documented that artifact streaming remains Python ASGI `StreamingResponse` (1MB chunks) with standard library `hashlib.sha256`.
3. Clarified that Rust strictly accelerates HTTP `Range` header parsing (`fast_parse_range_header`) and verified it with runtime invocation counters (`native_range_parse_calls_total`).

### Verification
- `native_range_parse_calls_total` counter verified in integration tests and E2E benchmark (55 calls recorded).
- Absence of SIMD SHA-256 formally acknowledged in `docs/NATIVE-INTERACTION-RUNTIME-AUDIT.md` and `docs/architecture/rust-mcp-interaction-engine.md`.

### Prevention rule
> **Never accept architectural claims as evidence of runtime behavior.** Every performance or native capability claim must be guarded by runtime invocation counters and explicit regression tests.

### Reusable lesson
Across all hybrid Python/Rust architectures, maintain a machine-checkable inventory linking documented claims directly to runtime metrics and test assertions.

### Related code
- `src/marketing_mcp/http/artifacts.py`
- `crates/marketing_mcp_fast/src/engine.rs`
- `docs/NATIVE-INTERACTION-RUNTIME-AUDIT.md`

### Related tests
- `tests/integration/test_native_hot_path.py::test_native_range_parse_counter_increments_on_artifact_download`

### Related lessons
- [27-silent-rust-exclusion-in-production-packaging.md](./27-silent-rust-exclusion-in-production-packaging.md)
- [30-unconnected-edge-accelerators-and-llm-token-bloat.md](./30-unconnected-edge-accelerators-and-llm-token-bloat.md)

### Status
Resolved
