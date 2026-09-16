# Failure Lesson 31 — MCP Protocol Inversion & Unprotected Ingress Admission

**Date Encountered**: 2026-09-16  
**Component**: `crates/marketing_mcp_fast/src/engine.rs`, `marketing_mcp/http/safety.py`, `marketing_mcp/accelerators`  
**Severity**: High (Architectural Inversion / DoS vulnerability / Latency Inflation)  
**Impact Area**: MCP Request Ingress / Protocol Framing / Resource Protection  

---

## 1. Executive Summary

In the legacy architecture, the native Rust extension sat at the very bottom of the execution stack as an optional leaf accelerator. All client requests were fully ingested, parsed into heavy Python dictionaries, and passed through multiple Starlette middleware layers before basic protocol validation or size checks occurred.

When an AI client sent an oversized, malformed, or invalid JSON-RPC payload, the Python runtime spent CPU cycles allocating objects, parsing strings, and running garbage collection before returning an error.

---

## 2. Root Cause Analysis

1. **Protocol Inversion**: In an agentic MCP interaction loop, request validation, admission, framing checks, and correlation IDs are transport concerns, not domain-science concerns. Delegating them to Python tool handlers caused latency inflation on every request.
2. **Missing Ingress Gate in Native Code**: There was no lightweight native layer to reject corrupt JSON, enforce payload boundaries ($\le 50\text{ MB}$), or assign tracking correlation IDs before Python object allocation.

---

## 3. Resolution & Hardening

1. **Native MCP Interaction Engine (`engine.rs`)**:
   - Implemented `admit_and_validate_request` in native Rust.
   - Rejects oversized requests (`PAYLOAD_TOO_LARGE`) instantly without Python heap allocation.
   - Validates JSON-RPC 2.0 framing and extracts `method`, `tool_name`, and `request_id` (`req-xxxx`).
2. **Fidelity-Preserving Error Model**:
   - Emits structured `NormalizedEngineError` directly matching the Python domain error taxonomy (`code`, `category`, `message`, `error_id`, `request_id`, `tenant_id`, `retryable`, `actionable`).
3. **Transparent Fallback**:
   - Implemented `_py_fast_admit_request` with 100% behavioral equivalence when native Rust is absent.

---

## 4. Architectural Invariants Established

1. **Fast-Reject Ingress Invariant**: Malformed or oversized requests must be admitted or rejected at the transport boundary before heavy domain or scientific Python objects are allocated.
2. **Zero Error Semantic Loss**: Transport-level rejections must carry the canonical `NormalizedError` payload structure so AI clients can programmatically handle retryability.
