# Failure Lesson 16: P0 Server API Key Exposure Through Artifact Sandbox Export

## 1. Executive Summary & Context
- **Component**: `src/marketing_mcp/storage/artifacts.py`, `src/marketing_mcp/mcp/tools/artifacts.py`, `src/marketing_mcp/http/artifacts.py`
- **Severity**: P0 Critical Security (Privilege Escalation & Credential Exposure)
- **Symptom**: When signed GCS URLs were unavailable, `export_artifact_to_sandbox` returned curl commands and Python snippets embedding `Authorization: Bearer <MARKETING_MCP_API_KEY>` directly to read-scoped (`marketing:read`) users.

## 2. Root Cause Analysis
- The tool read `MARKETING_MCP_API_KEY` from the server process environment and passed it into the fallback client snippet generation.
- Because `marketing:read` users can invoke `export_artifact_to_sandbox`, a read-only caller could acquire the server master key and escalate to admin/write permissions across the entire platform.

## 3. Resolution & Fix
- Eliminated reading and passing `MARKETING_MCP_API_KEY` into `export_to_sandbox`.
- Implemented `generate_artifact_download_token`: a short-lived (TTL 24h), single-artifact HMAC-SHA256 token tied exclusively to the target artifact digest and namespace.
- Added token verification in `/artifacts/{namespace}/{digest}/download`.
- Generated download commands and snippets use the single-use token query parameter without exposing server secrets.

## 4. Verification & Prevention
- Verified via `tests/integration/test_wave0_wave1_universal_and_security.py::test_export_artifact_never_leaks_server_api_key` (PASS).
