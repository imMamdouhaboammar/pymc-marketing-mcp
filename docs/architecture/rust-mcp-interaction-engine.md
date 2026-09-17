# Architecture Specification: Rust MCP Interaction Engine

> **Status: target-state design, not current-state evidence.** Several sections below are
> intentionally aspirational. Use `docs/NATIVE-INTERACTION-RUNTIME-AUDIT.md` for the traced
> production path and per-capability implementation status. In particular, native wire
> serialization, typed dispatch, Rust streaming/backpressure, and SIMD SHA-256 are not current.

## 1. System Overview & Core Invariants

The Model Context Protocol (MCP) server for PyMC-Marketing (`pymc-marketing-mcp`) provides AI clients (Claude, Cursor, ChatGPT) with a decision-safe interface for Bayesian marketing science.

### Hard Architectural Invariant
> **Repository Invariant**: Rust may accelerate transport, protocol handling, serialization, parsing, compression, streaming, deterministic numeric primitives, artifact I/O, and other performance-sensitive infrastructure. Python and established scientific libraries (`PyMC`, `PyMC-Marketing`, `ArviZ`, `xarray`, `NumPy`) remain the **sole authority** for statistical semantics, model diagnostics, model acceptance, optimization semantics, calibration semantics, and decision-safety policy. Rust must **never** independently decide whether a model is statistically acceptable.

---

## 2. Current Architecture vs. Target Architecture

### Current Architecture (Architectural Inversion)
```text
AI Client (JSON-RPC)
       │
       ▼
Python FastMCP / Starlette Server (cli.py, server.py)
       │
       ▼
Python Tool Handlers (tools/mmm.py, tools/datasets.py)
       │
       ▼
Python Domain Services (dataset_service, decision_service)
       │
       ▼ (Optional leaf acceleration)
crates/marketing_mcp_fast (PyO3)
  ├── sniff_and_validate_csv
  ├── compute_quantiles
  ├── evaluate_mcmc_gates (Duplicates Python statistical policy!)
  ├── compute_split_rhat (Duplicates ArviZ!)
  └── fast_serialize_json (Calls back into Python json.dumps!)
```

**Flaws in Current Architecture**:
1. **Rust below Python**: Rust is merely an optional leaf accelerator for individual functions, rather than managing the high-frequency client interaction boundary.
2. **Duplicated Statistical Authority**: `evaluate_mcmc_gates` in Rust implements hardcoded R-hat/ESS thresholds that conflict with Python's rich `diagnose_inferencedata`.
3. **Pseudonative Serialization**: `fast_serialize_json` invokes `json.dumps` back in Python, adding FFI boundary penalties.
4. **Packaging Omission**: The production Dockerfile and Python wheels do not build or bundle the native library.
5. **Dormant Accelerators**: LTTB curve compression and sparklines are not connected to transport responses.

### Target Architecture (Hardened Interaction Engine)
```text
AI Client (Cursor / Claude / ChatGPT)
       │
       │ MCP Streamable HTTP / stdio (JSON-RPC)
       ▼
┌─────────────────────────────────────────────────────────────┐
│                Rust MCP Interaction Engine                  │
│               (crates/marketing_mcp_fast)                   │
├─────────────────────────────────────────────────────────────┤
│ • Protocol Framing & Size Enforcement (10 MB request limit) │
│ • Early Malformed Payload Fast-Rejection                    │
│ • Correlation & Request ID Tracking                         │
│ • Zero-Copy Native JSON Serialization (serde_json)          │
│ • LTTB Transport Compression for Dense Curves               │
│ • HTTP Range-Header Parsing (fast_parse_range_header)       │
│ • Truthful Job Admission & Cancellation Acknowledgment      │
└──────────────────────────────┬──────────────────────────────┘
                               │
                               │ Typed Python Boundary (PyO3)
                               │ (BoundaryRequest -> BoundaryResponse)
                               │ (InteractionRequest -> InteractionResponse)
                               ▼
┌─────────────────────────────────────────────────────────────┐
│                 Python Application Services                 │
│                 (services/*, domain/*)                      │
├─────────────────────────────────────────────────────────────┤
│ • Dataset Registration & Semantic Schema Validation         │
│ • Async Job Lifecycle State Machine (SQLite)                │
│ • Centralized Authorization Policy & Tenant Isolation       │
│ • Error Normalization & Boundary Telemetry                  │
└──────────────────────────────┬──────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────┐
│               Scientific Computing Authority                │
│               (Python Scientific Stack)                     │
├─────────────────────────────────────────────────────────────┤
│ • PyMC-Marketing (MMM, CLV, Adstock, Saturation)            │
│ • PyMC (NUTS MCMC Sampling, Prior Sensitivity)              │
│ • ArviZ (Posterior Summary, Canonical R-hat, Bulk ESS)      │
│ • SciPy / NumPy (SLSQP Budget Optimization, Line Searches)   │
│ • NetCDF4 / xarray (Full-Fidelity Posterior Storage)        │
└─────────────────────────────────────────────────────────────┘
```

---

## 3. Division of Responsibilities

### Rust Owns:
- Raw byte validation, delimiter detection, and CSV parsing preflight.
- MCP protocol framing and JSON-RPC structure verification.
- Enforcing request size limits (10 MB aligned) and early malformed request rejection.
- Zero-copy JSON serialization of typed envelopes via `serde_json`.
- LTTB downsampling of visual curves for transport representations.
- HTTP 206 Partial Content Range header parsing via `fast_parse_range_header`.
- Sub-millisecond async job admission check (`fast_admit_job`) with `adm-*` interaction tokens.
- Interaction-level cancellation tracking.

### Python Owns:
- Statistical marketing-science models (MMM, CLV, priors, posteriors).
- MCMC sampling convergence evaluation and decision gate thresholds (`diagnose_inferencedata`).
- Model acceptance, caution, or rejection.
- Budget optimization objective formulations and constraints.
- Multi-tenant data authorization, credential evaluation, and scopes.
- Canonical error classification and diagnostic registry.
- Actual thread/process computation interruption on cancellation.

---

## 4. Typed Boundary Contract

Communication between the Rust interaction engine and Python application services occurs over a structured, typed interface:

```rust
pub struct InteractionRequest {
    pub request_id: String,
    pub tool_name: String,
    pub arguments_json: String,
    pub tenant_id: Option<String>,
    pub deadline_ms: Option<u64>,
}

pub struct InteractionResponse {
    pub correlation_id: String,
    pub status: String, // "ok", "error", "accepted"
    pub payload_json: String,
    pub execution_time_ms: f64,
}
```

In Python:
```python
@dataclass(frozen=True)
class BoundaryRequest:
    request_id: str
    tool_name: str
    arguments: dict[str, Any]
    tenant_id: str | None
    deadline_ms: int | None

@dataclass(frozen=True)
class BoundaryResponse:
    correlation_id: str
    success: bool
    data: dict[str, Any] | None
    error: dict[str, Any] | None
    execution_time_ms: float
```

---

## 5. Data, Error, Job & Cancellation Flows

### Data Flow
1. **Inbound**: The HTTP/stdio payload arrives as raw bytes. Rust validates content-length ($\le 10\text{ MB}$) and parses JSON framing in native memory.
2. **Dispatch**: Rust maps `tool_name` to the Python handler, passing normalized arguments via `BoundaryRequest` / `InteractionRequest`.
3. **Computation**: Python executes domain logic or queries the database.
4. **Outbound**: Python passes the resulting envelope to Rust; Rust applies LTTB compression to any large curves, computes unicode sparklines for metrics, and serializes the final envelope directly to bytes with `serde_json`.

### Error Normalization Flow
- Python `NormalizedError` instances retain full fidelity across the boundary:
  `error_code`, `category`, `error_id`, `request_id`, `job_id`, `dataset_id`, `model_id`, `tenant_id`, `retryable`, `actionable`.
- Rust transport errors (`REQUEST_TOO_LARGE`, `INVALID_JSON_RPC`, `TIMEOUT`) emit the exact same normalized JSON schema as Python errors.

### Job & Cancellation Flow
1. **Submission**: AI Client requests `submit_fit_mmm_job`. Rust admits request, generates interaction-level `adm-xxxx` token, validates payload bounds, registers the pending job in Python JobService (which assigns the canonical `job-xxxx` ID), and returns queued status.
2. **Polling**: Client calls `poll_job_progress`. Python returns current progress directly from the repository.
3. **Cancellation**: If client calls `cancel_job`, Python JobService transitions the job to `cancelling`, and Rust `fast_acknowledge_cancellation` fences and acknowledges the state. A job transitions to terminal `cancelled` once the worker observes cancellation.

---

## 6. Streaming & Artifact Delivery

- **Range Requests (HTTP 206)**: Rust parses `Range: bytes=start-end` via `fast_parse_range_header`, validating against file size.
- **Streaming & Cryptographic Audit**: Artifact delivery uses Python ASGI `StreamingResponse` (1MB chunks) with backpressure managed by the ASGI server. Hashing uses Python standard library `hashlib.sha256` (SIMD SHA-256 claims are removed as ungrounded).

---

## 7. Security Implications

- **Tenant Isolation**: Every request carries `tenant_id`. Rust never bypasses tenant checks; authorization remains strictly governed by Python `authorize_model` and `require_scope`.
- **Memory Safety**: All native code uses `#![forbid(unsafe_code)]` or strictly audited safe PyO3 constructs. No unhandled Rust panic can cross the FFI boundary or terminate the Python runtime.

---

## 8. Fallback Strategy

If the native extension fails to compile or is unavailable:
1. `is_rust_accelerated()` returns `False`.
2. Clean, verified pure Python routines execute with 100% behavioral equivalence.
3. The server logs an operational warning and exposes `"backend": "python-standard"` on `/health`.

---

## 9. Packaging & Deployment Strategy

- **Multi-Stage Dockerfile**:
  - Stage 1: `rust:1-slim` compiles the Rust extension with `cargo build --release`.
  - Stage 2: `python:3.12-slim` installs dependencies via `uv`, copies the compiled extension (`.so`), and asserts `is_rust_accelerated() is True`.
- **Runtime Check**: `/health` and `/ready` endpoints verify native engine activation in production.

---

## 10. Benchmarking & Verification Strategy

- Automated parity tests for all dual-path algorithms (quantiles, CSV preflight, sparklines, curve downsampling).
- Statistical invariance verification ensuring identical decisions between Rust ON and OFF.
- Latency benchmarks comparing p50, p95, wall-clock time, and memory usage across 6 payload classes.
