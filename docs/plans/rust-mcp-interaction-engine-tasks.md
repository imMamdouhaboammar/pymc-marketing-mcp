# Task Breakdown: Rust MCP Interaction Engine & Production Hardening

## Overview
This document tracks atomic, verifiable tasks across the 6 implementation slices. Every completed milestone is verified against test suites and codified into `Failure-lessons/`.

---

## Slice 1: Correct Current Rust Responsibilities & Parity Testing
- [x] **Task 1.1**: Audit and decouple `evaluate_mcmc_gates` from production decision path; demote `compute_split_rhat` to internal test fixture.
- [x] **Task 1.2**: Fix Python fallback defect in `_py_fast_mcmc_diagnostics` (`failures.push` -> `failures.append`).
- [x] **Task 1.3**: Add comprehensive property-based tests for `fast_compute_quantiles` (NaN, Infinity, empty array, constant vectors, extreme values) against NumPy.
- [x] **Task 1.4**: Add parity tests for `compress_curve_lttb` and `generate_sparkline` ensuring identical behavior between Rust and Python.
- [x] **Task 1.5**: Author `Failure-lessons/28-statistical-authority-duplication-and-fallback-attribute-error.md` and update index.

---

## Slice 2: Native JSON Serialization Path
- [x] **Task 2.1**: Remove Python `json.dumps` round-trip in `fast_serialize_json` in `crates/marketing_mcp_fast/src/lib.rs`.
- [x] **Task 2.2**: Implement real native `serde_json` serialization directly producing bytes/strings from Rust-side typed structures.
- [x] **Task 2.3**: Benchmark native serialization against pure Python across small (<1KB), medium (10KB), and large (>1MB) payloads.
- [x] **Task 2.4**: Author `Failure-lessons/29-pseudonative-serialization-roundtrip-penalty.md` and update index.

---

## Slice 3: Production Docker & Packaging Hardening
- [x] **Task 3.1**: Update `Dockerfile` to implement a multi-stage build (Stage 1 Rust builder, Stage 2 Python runtime with compiled extension).
- [x] **Task 3.2**: Configure automatic `.so` / `.dylib` placement in `src/marketing_mcp/accelerators/` so manual copying is eliminated.
- [x] **Task 3.3**: Update `/health` and `/ready` endpoints in `src/marketing_mcp/cli.py` and `health.py` to expose active interaction engine backend and version.
- [x] **Task 3.4**: Configure GitHub Actions / CI workflow lanes for Rust unit/clippy, Native bridge, Fallback, and Docker container verification.
- [x] **Task 3.5**: Author `Failure-lessons/27-silent-rust-exclusion-in-production-packaging.md` and update index.

---

## Slice 4: Rust MCP Interaction Engine Core (Admission & Routing)
- [x] **Task 4.1**: Expand `crates/marketing_mcp_fast` to introduce `engine` module with request admission, size validation (max 50MB), and correlation IDs.
- [x] **Task 4.2**: Implement early malformed JSON-RPC rejection in native code.
- [x] **Task 4.3**: Design typed boundary bridge between Rust and Python passing normalized arguments, tenant ID, and execution deadline.
- [x] **Task 4.4**: Integrate `NormalizedError` taxonomy into native transport errors preserving error IDs and diagnostic details.
- [x] **Task 4.5**: Author `Failure-lessons/31-mcp-protocol-inversion-and-admission-boundary.md` and update index.

---

## Slice 5: Streaming, Compression & Artifact Delivery
- [x] **Task 5.1**: Connect `compress_curve_lttb` to `get_response_curves` in `decision_service.py` and `adapters/pymc_marketing.py` for token-efficient transport envelopes.
- [x] **Task 5.2**: Connect `generate_sparkline` to dataset column spend telemetry envelopes.
- [x] **Task 5.3**: Implement native HTTP Range request (206) slice parsing and streaming file transfer.
- [x] **Task 5.4**: Implement native SIMD SHA-256 chunked hashing for artifact integrity.
- [x] **Task 5.5**: Author `Failure-lessons/30-unconnected-edge-accelerators-and-llm-token-bloat.md` and update index.

---

## Slice 6: Async Jobs & Truthful Cancellation
- [x] **Task 6.1**: Implement sub-millisecond job submission acknowledgment (`status: "accepted"`, `job_id`).
- [x] **Task 6.2**: Implement bounded status polling with fast cached responses.
- [x] **Task 6.3**: Implement truthful cancellation propagation to Python asyncio background task / worker fence.
- [x] **Task 6.4**: Author `Failure-lessons/32-deceptive-cancellation-and-orphan-compute-fence.md` and update index.

---

## Final Verification & Mission Deliverables
- [x] **Task 7.1**: Run full statistical invariance test suite asserting identical decisions with Rust ON vs. OFF.
- [x] **Task 7.2**: Run full platform regression suite (Rust tests, bridge tests, fallback tests, security tests).
- [x] **Task 7.3**: Run end-to-end performance benchmarks comparing Python-only vs. Rust-enabled runtime.
- [x] **Task 7.4**: Produce the comprehensive 14-section Final Mission Report.
