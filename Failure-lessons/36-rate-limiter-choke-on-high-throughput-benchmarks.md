# Lesson 36: Rate-Limiter Choke on High-Throughput Benchmarks

### Context
Fast end-to-end benchmarking of streamable HTTP MCP tools (`scripts/benchmark_mcp_end_to_end.py`) against `RequestSafetyMiddleware`.

### What happened
Running automated 50-iteration benchmarks across 7 MCP scenarios caused the client session to abruptly fail with `HTTP 429 Too Many Requests` (`mcp.shared.exceptions.MCPError: Server returned an error response`).

### Observable symptom
Benchmark client received HTTP 429 after ~120 requests during the dataset inspection scenario, crashing the benchmark runner.

### Impact
Blocked end-to-end performance benchmarking and created false impressions of server instability under test load.

### Incorrect assumption
Implicitly assumed client requests would never exceed 120 requests/minute in local evaluation environments.

### Root cause
**Confirmed**. `RequestSafetyMiddleware` hardcoded `requests_per_minute: int = 120` without exposing a configurable parameter in `Settings` or `create_http_app`.

### Why the architecture allowed it
Security middleware was instantiated with static defaults without an interface to tune thresholds for testing, benchmarking, or high-throughput batch workloads.

### Fix
Added `rate_limit_per_minute: int = Field(default=120)` to `Settings` in `src/marketing_mcp/config.py`, passed `requests_per_minute=getattr(actual_settings, "rate_limit_per_minute", 120)` when adding `RequestSafetyMiddleware` in `src/marketing_mcp/cli.py`, and configured `rate_limit_per_minute=100000` in `scripts/benchmark_mcp_end_to_end.py`.

### Verification
50 iterations with 5 warmups across all 7 scenarios ran cleanly without 429 errors, completing in ~3.5 seconds (`mcp-e2e-benchmark.json`).

### Prevention rule
> **Protection middleware (rate limits, request timeouts, size caps) must always be parameterized via configuration settings with safe production defaults and tunable test/benchmark overrides.**

### Reusable lesson
Never hardcode rate limits or throttling thresholds in middleware constructors without configuration bindings.

### Related code
- `src/marketing_mcp/http/safety.py`
- `src/marketing_mcp/config.py`
- `src/marketing_mcp/cli.py`
- `scripts/benchmark_mcp_end_to_end.py`

### Related tests
- `tests/integration/test_native_hot_path.py`
- `scripts/benchmark_mcp_end_to_end.py`

### Related lessons
- [01-fail-closed-anonymous-http-binding.md](./01-fail-closed-anonymous-http-binding.md)
- [17-dataset-ingestion-ssrf-and-memory-exhaustion.md](./17-dataset-ingestion-ssrf-and-memory-exhaustion.md)

### Status
Resolved
