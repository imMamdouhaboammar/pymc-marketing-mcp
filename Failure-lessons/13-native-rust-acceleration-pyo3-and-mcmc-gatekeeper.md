# Failure Lesson 13: Native Rust C-Extension Acceleration, PyO3 Dynamic Linking & MCMC Diagnostic Gatekeeper

- **Date**: 2026-09-16
- **Component**: `crates/marketing_mcp_fast`, `marketing_mcp/accelerators`, `dataset_service`, `decision_service`
- **Severity**: P1 Performance & LLM Latency Friction
- **Root Cause**: High deserialization and validation latency in pure Python/Pandas on medium-to-large datasets; PyO3 `cdylib` missing dynamic symbol resolution on Darwin; and silent statistical false-greens when chain within-variance is near zero.

---

## 1. Executive Summary & Context

Autonomous AI agents (Claude, Cursor, ChatGPT) interact with `pymc-marketing-mcp` via the Model Context Protocol (MCP) in conversational loops. In standard Python/Pandas implementations:
1. Validating and sniffing a 3,000-row x 10-column CSV dataset consumed **~3.70 seconds** (per Post-Mortem 07), causing tool call lag and context timeouts.
2. In-memory posterior extraction across thousands of MCMC draws generated excessive token consumption and high latency.
3. Unconverged MCMC sampling fits were evaluated lazily downstream, causing agents to attempt budget optimization or scenario simulations on degenerate models.

To resolve these friction points without violating the core invariant (**zero mathematical reimplementation of PyMC-Marketing models in Rust**), a high-performance native Rust accelerator (`marketing_mcp_fast`) and PyO3 C-extension bridge were introduced.

---

## 2. Symptoms & Failure Modes

### Failure Mode A: SIMD Preflight vs. Heavy Pandas Ingestion
- **Symptom**: Calling `register_dataset` or `validate_dataset` on raw bytes forced pandas DataFrame instantiation, multi-pass type inference, and repeated datetime parsing before basic feasibility was verified.
- **Impact**: AI client waiting 3.7+ seconds before discovering a basic syntax error, negative spend value, or missing date column.

### Failure Mode B: PyO3 macOS Dynamic Linker Abort
- **Symptom**: Building `cdylib` with standard `cargo build --release` and importing into Python resulted in runtime abort:
  ```text
  dyld[63452]: symbol not found in flat namespace '_PyBaseObject_Type'
  error: test failed, to rerun pass `--lib`
  ```
- **Root Cause**: On macOS (Mach-O), Python C-extensions cannot link statically to `libpython.dylib`. They must use dynamic lookup (`-undefined dynamic_lookup`). Furthermore, running `cargo test` on a crate with `pyo3 = { features = ["extension-module"] }` prevents cargo from linking to python symbols.

### Failure Mode C: Split $\hat{R}$ False-Green on Degenerate Constant Chains
- **Symptom**: In Gelman-Rubin split $\hat{R}$ calculation, if two chains both become stuck at different constants (e.g. Chain 1 = `0.0`, Chain 2 = `100.0`), within-chain variance $W \le 10^{-12}$.
- **Root Cause**: A naïve implementation checking `if w <= 1e-12 { return 1.0; }` returned $\hat{R} = 1.0$ (perfect convergence), falsely approving a catastrophically unconverged model!

### Failure Mode D: LLM Context Token Exhaustion on Dense Curves
- **Symptom**: Exporting saturation and response curve trajectories with 1,000+ $(x, y)$ coordinate pairs flooded LLM context windows, wasting token quotas and slowing down generation.

---

## 3. Architecture & Resolution

```text
┌─────────────────────────────────────────────────────────────┐
│                    AI Client (Cursor / Claude)              │
└──────────────────────────────┬──────────────────────────────┘
                               │ MCP Tool Call (JSON-RPC)
                               ▼
┌─────────────────────────────────────────────────────────────┐
│                 Python FastMCP Transport Layer              │
│                 (dataset_service, decision_service)         │
└──────────────────────────────┬──────────────────────────────┘
                               │
                ┌──────────────┴──────────────┐
                ▼                             ▼
   ┌──────────────────────────┐  ┌──────────────────────────┐
   │ Native Rust Accelerator  │  │  Pure Python Fallback    │
   │ (marketing_mcp_fast.so)  │  │  (Zero-Downtime Parity)  │
   ├──────────────────────────┤  ├──────────────────────────┤
   │ • SIMD CSV Preflight     │  │ • Bounded Pandas Sniff   │
   │ • 0.1ms Diagnostic Gates │  │ • SciPy / NumPy Stats    │
   │ • Quantiles & HDI        │  │ • Python LTTB            │
   │ • LTTB Curve Compression │  │ • Unicode Sparklines     │
   │ • Unicode Sparklines     │  └──────────────────────────┘
   └──────────────────────────┘
```

### 1. SIMD CSV Sniffer (`crates/marketing_mcp_fast/src/csv_preflight.rs`)
Preflights raw byte buffers in a single SIMD pass using `csv` and `memchr`:
- Sniffs headers, counts rows, detects null representations (`nan`, `null`, empty).
- Computes min, max, mean, and validates non-negative spend on channel columns.
- Validates ISO-8601 date bounds.
- **Benchmark**: Validating 3,000 rows x 10 columns dropped from **3,700 ms** to **1.31 ms** (**~2,800x speedup**).

### 2. PyO3 Cargo & Linker Configuration
In `crates/marketing_mcp_fast/Cargo.toml`:
```toml
[lib]
name = "marketing_mcp_fast"
crate-type = ["cdylib", "rlib"]

[dependencies]
pyo3 = { version = "0.23" }
serde = { version = "1.0", features = ["derive"] }
serde_json = "1.0"
rayon = "1.10"
csv = "1.3"
memchr = "2.7"

[features]
default = ["extension-module"]
extension-module = ["pyo3/extension-module"]
```
- Build command for cdylib: `RUSTFLAGS="-C link-arg=-undefined -C link-arg=dynamic_lookup" cargo build --release`.
- Unit test command in Rust: `cargo test --no-default-features` (links dynamically against active virtualenv python).

### 3. Hardened Split $\hat{R}$ Diagnostics Gatekeeper (`diagnostics.rs`)
Fixed split $\hat{R}$ calculation to handle degenerate zero within-chain variance:
```rust
let overall_mean: f64 = chain_means.iter().sum::<f64>() / m;
let b_over_n = chain_means.iter().map(|&x| (x - overall_mean).powi(2)).sum::<f64>() / (m - 1.0);
let w: f64 = chain_vars.iter().sum::<f64>() / m;

if w <= 1e-12 {
    if b_over_n > 1e-12 {
        // Different constants across chains: massive failure
        return 999.0;
    }
    return 1.0;
}

let var_plus = ((n - 1.0) / n) * w + b_over_n;
(var_plus / w).sqrt()
```
Instantly classifies models into `approved`, `caution`, or `rejected`, rejecting unconverged models in **0.10 ms** before running downstream budget optimizations.

### 4. LTTB Compression & Unicode Sparklines (`sparklines.rs`)
- Implemented the Largest-Triangle-Three-Buckets (LTTB) downsampling algorithm, compressing dense 1,000-point response curves to 25–50 geometrically representative points.
- Implemented Unicode block sparklines (` ▂▃▄▅▆▇█`) for inline LLM summaries.

### 5. Zero-Downtime Pure Python Fallback (`marketing_mcp/accelerators/__init__.py`)
- Every accelerator function wraps native calls in `try...except ImportError, AttributeError`.
- If the compiled `.so` is not present (e.g. lightweight developer environments without Rust), identical pure Python routines execute with 100% test parity.

---

## 4. Verification Evidence & Invariants

| Suite | Tests | Result |
| :--- | :---: | :---: |
| Native Rust Unit Tests (`cargo test --no-default-features`) | 14 passed | ✅ PASS (0.01s) |
| Python Accelerator Bridge (`test_rust_bridge.py`, `test_fast_csv_preflight.py`, `test_fast_diagnostics.py`) | 14 passed | ✅ PASS (0.08s) |
| Live MCP Integration (`test_mcp_rust_acceleration_e2e.py`) | 2 passed | ✅ PASS (3.50s) |
| Pure Python Parity (`test_pure_python_fallback_parity`) | Verified | ✅ PASS |
| Non-statistical Regression Suite | 546 passed | ✅ PASS (28.37s) |

---

## 5. Architectural Invariants Established

1. **Zero Math Reimplementation Invariant**: Core PyMC-Marketing statistical models (NUTS MCMC, priors, adstock, saturation formulas) remain 100% in Python. Rust is strictly an edge accelerator for I/O sniffing, diagnostic gatekeeping, quantiles, and token compression.
2. **Transparent Fallback Invariant**: The presence of the Rust C-extension must never be a hard runtime requirement for platform functionality; pure Python fallbacks must always achieve 100% behavioral equivalence.
3. **Fail-Closed Diagnostic Invariant**: Degenerate sampler states (zero within-chain variance with separated means) must evaluate to critical non-convergence ($\hat{R} \ge 999$) and block downstream decision tools.
