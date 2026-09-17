# Native Interaction Runtime Audit

Status: current working-tree audit; implementation evidence, not release approval.

## Decision

The official Python MCP SDK remains the protocol server. Rust participates in selected
interaction hot paths through PyO3. The HTTP admission path intentionally performs native
framing validation before the SDK parses the same payload. The SDK exposes no supported
hook for injecting the already parsed request, so parsed-object handoff is not implemented.

The duplication is retained for bounded-memory admission and early malformed/oversized
request rejection. It is not described as a wire-latency speedup. Run
`scripts/benchmark_native_admission.py` to measure its incremental cost on the target host.

Native serde is not used for Python-originating MCP envelopes. Existing measurements show
PyO3 object traversal is slower than CPython JSON encoding, and FastMCP owns final JSON-RPC
encoding. `env_json()` is therefore a helper/benchmark surface, not production wire proof.

## Measured end-to-end evidence

A local 2026-09-16 run of `scripts/benchmark_mcp_end_to_end.py --iterations 50
--warmup 5` exercised Uvicorn, Streamable HTTP/SSE, MCP initialization, SDK dispatch, and
`get_model_status` tool calls. Rust recorded 58 admission calls and zero fallbacks.

| Backend | p50 | p95 | p99 | Throughput | CPU | Peak RSS |
|---|---:|---:|---:|---:|---:|---:|
| Python fallback | 4.396 ms | 4.624 ms | 4.728 ms | 101.10 req/s | 0.229 s | 299.3 MiB |
| Rust admission | 4.387 ms | 5.363 ms | 5.540 ms | 100.98 req/s | 0.238 s | 299.8 MiB |

This small local workload proves production-path invocation and parity, not a speedup. It
shows effectively neutral median latency with noisier Rust tail latency. Release decisions
require repeated CI/container runs and representative large-payload and concurrent loads.

## HTTP production path

```text
client bytes
-> Starlette application
-> MCPAuthMiddleware (authentication/context)
-> NativeAdmissionMiddleware (bounded ASGI receive + fast_admit_request)
-> RequestSafetyMiddleware (Content-Length precheck, rate limit, correlation header)
-> MCP SDK StreamableHTTP session manager
-> SDK JSON-RPC parse and dispatch
-> registered tool handler
-> Application service
-> env() / ToolEnvelope.model_dump()
-> MCP SDK content conversion and JSON encoding
-> ASGI HTTP response
```
| Boundary | Current implementation | Rust | Python parse | Duplicate allocation/parse | Value |
|---|---|---:|---:|---:|---|
| ASGI body receive | bounded chunk accumulation, 10 MiB cap | no | no | one joined body | resource safety |
| Admission | serde_json framing/protocol validation | yes | no | full parse precedes SDK parse | early rejection |
| Authentication | canonical Python middleware | no | no | no | security authority |
| MCP dispatch | official Python MCP SDK | no | yes | second JSON parse | compatibility |
| Tool/service | Python handlers and services | selective helpers | yes | normal objects | scientific authority |
| Envelope | Pydantic model dump | no | yes | normal objects | typed public contract |
| Wire encode | MCP SDK | no | yes | one final encode | protocol compatibility |

The admission metadata attached to ASGI state is observational only. It never grants
authorization and cannot bypass Python scope, tenant, dataset, model, artifact, or job checks.

## stdio path

```text
stdio bytes -> Python MCP SDK parse -> dispatch -> Python tool/service -> SDK encode -> stdout
```

Rust admission is not in stdio. Statistical and public tool semantics must remain identical
with `MARKETING_MCP_DISABLE_RUST=1`. The CI fallback lane executes this mode explicitly.

## Jobs

```text
tools/call -> Python scope check -> native payload admission token
-> Python JobService creates canonical job_id -> repository -> executor/worker
-> poll reads canonical repository state
-> cancel authorizes and transitions canonical state
-> native interaction acknowledgment -> canonical state returned
```
The `adm-*` identifier is interaction-only and is never exposed as the persistent
`job_id`. A running job remains `cancelling` until the executor observes cancellation
and records `cancelled`. Queued work may become terminal immediately because no worker
is active. Late external-worker results are fenced by repository lease/fence tokens.

## Artifacts

```text
GET artifact -> Python token/principal authorization -> Python file metadata
-> native Range parser -> Python StreamingResponse -> 1 MiB Python file chunks
```

Range parsing is native and the production route has counter-backed integration evidence.
Streaming, hashing, backpressure, and chunk ownership remain Python. There is no native or
SIMD SHA-256 implementation and no Rust-owned bounded stream buffer.

## Response curves and large structured output

Python computes and retains canonical full-resolution curves. LTTB creates an additional
`transport_curve` representation only; it does not replace scientific inputs or stored
model output. Sparkline generation is presentation-only.

## Errors

Native admission errors map to JSON-RPC parse/invalid-request responses and preserve the
native code, error id, actionability, and valid request id where available. Python remains
the canonical domain/application error taxonomy. Native panic or stack internals are not
returned to clients.

## Capability status

| Requirement | Runtime caller | Evidence | Status |
|---|---|---|---|
| Native admission | POST /mcp middleware | counter + integration and real HTTP benchmark | IMPLEMENTED_AND_LOCALLY_VERIFIED |
| JSON-RPC validation | same | Rust + fallback parity tests | IMPLEMENTED_AND_VERIFIED |
| Native serialization | no final-wire caller | helper benchmark only | REMOVE_CURRENT_STATE_CLAIM |
| Typed dispatch boundary | none | documentation only | PLANNED |
| Job admission | submit_fit_mmm_job | admission-id contract tests | IMPLEMENTED_AND_VERIFIED |
| Cancellation | cancel_job + JobService | cancelling-to-cancelled test | IMPLEMENTED_AND_VERIFIED |
| LTTB | DecisionService.response_curves | bridge/service tests | IMPLEMENTED_NOT_YET_E2E_BENCHMARKED |
| Artifact Range | artifact download route | route counter assertion | IMPLEMENTED_AND_VERIFIED |
| Native artifact streaming | none | none | PLANNED_PENDING_BENCHMARK |
| Backpressure | Python/ASGI only | no native evidence | REMOVE_NATIVE_CLAIM |
| SIMD SHA-256 | none | no dependency or code | REMOVE_CLAIM |
| Rust ON/OFF parity | explicit environment switch | local full statistical matrix + CI matrix | IMPLEMENTED_AND_LOCALLY_VERIFIED |
| Docker activation | Docker build assertion | Docker CI smoke added; local daemon unavailable | IMPLEMENTED_EVIDENCE_PENDING |
| End-to-end MCP benchmarks | real HTTP/SSE tool call | ON/OFF p50/p95/p99, CPU, RSS, throughput | IMPLEMENTED_AND_LOCALLY_VERIFIED |

## Verification commands

```bash
uv sync --frozen --extra dev
uv run pytest tests/integration/test_native_hot_path.py tests/test_rust_bridge.py -q
uv run pytest tests/integration/test_large_artifacts_and_resilience.py -q
MARKETING_MCP_DISABLE_RUST=1 uv run pytest tests/integration/test_mcp_protocol.py -q
cargo fmt --check --manifest-path crates/marketing_mcp_fast/Cargo.toml
cargo clippy --all-targets --all-features --manifest-path crates/marketing_mcp_fast/Cargo.toml -- -D warnings
cargo test --manifest-path crates/marketing_mcp_fast/Cargo.toml
uv run python scripts/benchmark_native_admission.py --iterations 1000
uv run python scripts/benchmark_mcp_end_to_end.py --iterations 100 --warmup 10
```

Passing local commands are development evidence only. Release claims require exact-commit
CI and container evidence under `docs/release-evidence/`.
