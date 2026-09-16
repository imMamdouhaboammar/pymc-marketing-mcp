# Failure Lesson 29 — The PyO3 Serialization Overhead Trap & Native Boundary Placement

**Date Encountered**: 2026-09-16  
**Component**: `crates/marketing_mcp_fast/src/lib.rs`, `marketing_mcp/accelerators/__init__.py`  
**Severity**: Medium (Performance Inefficiency / Architecture Decision Boundary)  
**Impact Area**: FFI Boundary Overhead / Serialization Latency / Memory Allocation  

---

## 1. Executive Summary

An audit of `fast_serialize_json` revealed that the original implementation entered Rust via PyO3 only to import Python's standard library `json` module and invoke `json.dumps(obj)`.

To eliminate this round-trip, an in-memory recursive Rust serializer was implemented using `serde_json` and PyO3 downcasting (`PyDict`, `PyList`, `PyAny`). Rigorous empirical benchmarking across small (<1KB), medium (10KB), and large (1MB) payloads revealed a critical systems finding:

| Payload Class | Size | CPython `json.dumps` (C) | Rust PyO3 Traversal + `serde_json` | Latency Ratio |
| :--- | :---: | :---: | :---: | :---: |
| Small Dict | 55 B | **0.002 ms** | 0.004 ms | 2.0x slower in Rust |
| Medium Telemetry | 11 KB | **0.156 ms** | 0.396 ms | 2.5x slower in Rust |
| Large Dataset Summary | 1.05 MB | **10.58 ms** | 50.26 ms | 4.7x slower in Rust |

Converting Python object trees across the FFI boundary into `serde_json::Value` incurs massive allocation and downcasting overhead compared to CPython's native C-implemented `json.dumps`.

---

## 2. Root Cause Analysis

1. **CPython Internal C Integration**: CPython's `json.dumps` is written directly in C (`Modules/_json.c`) and operates directly on `PyObject*` struct pointers without foreign-function interface abstractions.
2. **PyO3 Conversion Cost**: Crossing the FFI boundary to inspect every dictionary key, convert strings to Rust `String`s, and allocate intermediary `serde_json::Value` enum nodes allocates substantially more heap memory than serializing directly in the runtime where the object resides.
3. **Where Native Serialization Wins**: Native serialization (`serde_json::to_vec` / `to_string`) is orders of magnitude faster **only when data originates in Rust** (e.g. `InteractionResponse`, CSV preflight results, streaming chunk headers, range indices).

---

## 3. Resolution & Architectural Policy

1. **Context-Aware Serialization Policy**:
   - **For Python-originating dictionaries**: Use CPython's C-accelerated `json.dumps` directly. Do not cross the FFI boundary simply to serialize.
   - **For Rust-originating structures**: Serialize directly in Rust using `serde_json::to_vec` to emit raw UTF-8 bytes without ever creating intermediate Python objects.
2. **Dynamic Loader Resolution**:
   - Fixed the dynamic loader in `src/marketing_mcp/accelerators/__init__.py` to use `ExtensionFileLoader` so `.dylib` files on macOS Darwin and `.so` files in package directories are loaded reliably.

---

## 4. Architectural Invariants Established

1. **FFI Allocation Invariant**: Never cross the Python/Rust boundary unless the computation performed inside Rust exceeds the cost of boundary traversal and object allocation.
2. **Native Bytes Streaming**: The Rust Interaction Engine emits JSON bytes directly from Rust structs; it does not materialize Python dictionaries first when preparing outbound MCP protocol frames.
