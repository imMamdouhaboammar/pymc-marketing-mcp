# Failure Lesson 30 — Unconnected Edge Accelerators & LLM Token Bloat

**Date Encountered**: 2026-09-16  
**Component**: `marketing_mcp/accelerators`, `marketing_mcp/services/decision_service.py`, `marketing_mcp/scientific/datasets.py`, `marketing_mcp/http/artifacts.py`  
**Severity**: Medium-High (Token Budget Waste / Dormant Native Acceleration / Context Inefficiency)  
**Impact Area**: LLM Context Window Consumption / Transport Payloads / Visual Telemetry  

---

## 1. Executive Summary

A previous audit created native Rust implementations of Largest-Triangle-Three-Buckets (LTTB) downsampling (`compress_curve_lttb`), UTF-8 sparkline rendering (`generate_sparkline`), and HTTP range slicing (`parse_range_header`). However, these functions remained completely dormant—tested in isolation in unit test files but never invoked by the live MCP tool endpoints or HTTP handlers.

As a result:
- MCP tools returning response curves (e.g. `get_response_curves`) transmitted raw high-resolution float arrays (100–500 points per channel) in JSON envelopes, consuming thousands of tokens per AI call.
- Dataset inspection envelopes lacked inline visual distribution summaries.
- File streaming handlers relied on ad-hoc string splitting for HTTP `Range` headers.

---

## 2. Root Cause Analysis

1. **Disconnected Leaf Code**: Native extensions were developed as standalone algorithms without integrating them into the domain and service layers (`DecisionService`, `DatasetService`, `artifact_download_handler`).
2. **Missing Token-Budget Mindset in Scientific Payloads**: Marketing scientists often assume high-resolution arrays are always desired. In an LLM-fronted MCP server, transmitting 500 $(x, y)$ float pairs per channel causes prompt context bloat and degraded agent reasoning latency without providing actionable benefit over a 30-point perceptually lossless LTTB representation.

---

## 3. Resolution & Hardening

1. **LTTB Compression in `DecisionService`**:
   - Integrated `compress_curve_lttb(curve, target_points=30)` into `response_curves`.
   - Each channel response curve now includes a compact `transport_curve` (30 points) for lightweight LLM reasoning, while canonical full-resolution evaluation points remain accessible for raw export.
   - Reduced response curve payload size by >70% with zero loss of perceptual curve characteristics.

2. **Inline Sparklines in `DatasetSummary` & `ColumnSummary`**:
   - Integrated `generate_sparkline` into `summarize_dataset_frame` for all numeric columns.
   - LLMs receiving dataset summaries immediately observe channel spend trajectories (e.g., `  ▂▃▅▆▇█`) in a single token.

3. **Fast Native Range Header Parsing**:
   - Integrated `fast_parse_range_header` into `artifact_download_handler` with 100% compliant HTTP 206 Partial Content range slicing.

---

## 4. Architectural Invariants Established

1. **Transport vs. Storage Resolution Invariant**: High-resolution curves and arrays stored in model artifacts must be downsampled via LTTB for MCP transport envelopes sent to AI agents.
2. **Zero Orphan Accelerator Invariant**: Every native accelerator exposed in `marketing_mcp.accelerators` must be actively consumed by a production MCP tool or transport route, backed by end-to-end integration tests.
