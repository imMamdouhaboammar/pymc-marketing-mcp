# Failure Lesson 17: P0 SSRF & Memory Exhaustion in Remote Dataset Ingestion

## 1. Executive Summary & Context
- **Component**: `src/marketing_mcp/mcp/tools/datasets.py`, `src/marketing_mcp/security/remote_fetch.py`
- **Severity**: P0 Critical Security (SSRF, Metadata Service Exposure, DoS)
- **Symptom**: `register_dataset(url=...)` accepted arbitrary HTTP/HTTPS destinations via unpinned `urllib.request.urlopen` and buffered entire responses into memory before enforcing size limits.

## 2. Root Cause Analysis
1. Direct network connections without DNS pre-resolution allowed requests to internal IPs (`127.0.0.1`, RFC1918 private subnets, cloud metadata `169.254.169.254`).
2. Automatic redirect handling allowed public endpoints to redirect silently to internal network targets.
3. Reading `resp.read()` unbounded allowed multi-gigabyte responses to trigger Out-Of-Memory (OOM) crashes before `max_dataset_mb` checks ran.

## 3. Resolution & Fix
- Introduced dedicated `safe_fetch_remote_dataset` with:
  - DNS pre-resolution rejecting loopback, private, link-local, multicast, and reserved IP ranges.
  - Strict redirect hop inspection (up to 5 hops), validating the IP of each target destination.
  - Streaming chunked reading (64KB chunks) with an active byte-counter that immediately aborts with `RESOURCE_LIMIT_EXCEEDED` if the limit is exceeded.
- Added strict `base64.b64decode(..., validate=True)` in `register_dataset`.

## 4. Verification & Prevention
- Verified via `tests/integration/test_wave0_wave1_universal_and_security.py::test_safe_fetch_remote_dataset_rejects_ssrf` (PASS).
