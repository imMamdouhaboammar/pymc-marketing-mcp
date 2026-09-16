# Implementation Plan: Rust MCP Interaction Engine & Production Hardening

## Overview & Background

The Model Context Protocol (MCP) server for PyMC-Marketing (`pymc-marketing-mcp`) must provide low-latency interaction, robust streaming, and backpressure for AI clients without altering the Bayesian statistical modeling authoritative in Python.

This plan details the phased migration from leaf accelerator functions to a fronting interaction engine while preserving full backward compatibility.

---

## Phases & Execution Slices

### Slice 1: Correct Existing Native Responsibilities & Fallback Hygiene
- **Goal**: Ensure Rust does not hold statistical authority or duplicate decision thresholds, fix Python fallback bugs, and establish property-based test parity.
- **Tasks**:
  1. Audit and remove `fast_mcmc_diagnostics` / `evaluate_mcmc_gates` from the production authority path.
  2. Demote `compute_split_rhat` to internal benchmark/comparison test utility with ArviZ as golden truth.
  3. Fix the Python fallback defect in `_py_fast_mcmc_diagnostics` (`failures.push` -> `failures.append`).
  4. Implement property-based and boundary parity tests for `fast_compute_quantiles` and `compress_curve_lttb` (handling `NaN`, `Inf`, empty slices, constant vectors).
  5. Codify **Failure Lesson 28**: Statistical Authority Duplication & Fallback AttributeError.

### Slice 2: True Native Serialization
- **Goal**: Replace the pseudo-native serialization round-trip with true native serde serialization.
- **Tasks**:
  1. Remove the PyO3 round-trip where Rust called back into Python `json.dumps`.
  2. Implement native serialization via `serde_json` for typed interaction structures directly to bytes.
  3. Benchmark serialization latency vs. Python `json.dumps` across small, medium, and large payloads.
  4. Codify **Failure Lesson 29**: Pseudonative Serialization Round-Trip Trap.

### Slice 3: Productionize Native Packaging & CI Verification
- **Goal**: Ensure the compiled extension is reliably built, bundled in Docker, and verified at runtime.
- **Tasks**:
  1. Update `Dockerfile` to use a multi-stage build:
     - Builder stage with Rust toolchain compiling `crates/marketing_mcp_fast`.
     - Runtime stage copying `.so` extension and validating `is_rust_accelerated() is True`.
  2. Expose runtime acceleration status on `/health` and `/ready` endpoints.
  3. Introduce 5 explicit CI test lanes: Rust unit/clippy, Native Python bridge, Python fallback, Parity verification, and Container verification.
  4. Codify **Failure Lesson 27**: Silent Rust Exclusion in Production Packaging.

### Slice 4: Rust MCP Interaction Engine Core
- **Goal**: Front the client interaction path with request admission, early rejection, and a typed Python bridge.
- **Tasks**:
  1. Structure `crates/marketing_mcp_fast` into modular engine components: `protocol`, `admission`, `routing`, `bridge`.
  2. Implement request size enforcement ($\le 50\text{ MB}$) and malformed JSON-RPC fast rejection.
  3. Establish typed boundary contract between Rust and Python with request ID generation and correlation tracking.
  4. Integrate error normalization ensuring full fidelity of `error_id`, `request_id`, `tenant_id`, and upstream cause chains.
  5. Codify **Failure Lesson 31**: MCP Protocol Inversion and Admission Boundary.

### Slice 5: Streaming, Compression & Artifact Delivery
- **Goal**: Connect dormant edge accelerators to live transport payloads and accelerate artifact transfers.
- **Tasks**:
  1. Connect LTTB compression to `get_response_curves` in `decision_service` to deliver compact (25–50 point) curve representations for AI clients while preserving full-resolution data in models.
  2. Connect sparklines to dataset column telemetry envelopes.
  3. Implement native chunked artifact streaming with HTTP 206 Partial Content range requests and SIMD SHA-256 calculation.
  4. Codify **Failure Lesson 30**: Unconnected Edge Accelerators and LLM Token Bloat.

### Slice 6: Async Jobs & Truthful Cancellation
- **Goal**: Sub-millisecond job acknowledgment and truthful cancellation propagation to Python compute workers.
- **Tasks**:
  1. Implement fast job submission acknowledgment (`status: "accepted"`, `job_id`).
  2. Implement bounded heartbeat status polling.
  3. Establish truthful cancellation contract: client disconnect or cancellation request marks interaction cancelled AND triggers cancellation in Python worker task fence.
  4. Codify **Failure Lesson 32**: Deceptive Cancellation and Orphan Compute Fence.

---

## Quality Gates & Verification Standards
1. **Zero Mathematical Alteration**: Models produce identical posterior traces and decisions with Rust ON vs. OFF.
2. **Panic Safety**: No panic may cross the FFI boundary; all native failures convert to normalized domain errors.
3. **100% Fallback Equivalence**: All external MCP contracts function identically when native acceleration is disabled.
