# Failure Lesson 23: P1 Default Tenant Listing Bypass & Inbox Metadata Leakage

## 1. Executive Summary & Context
- **Component**: `src/marketing_mcp/mcp/tools/datasets.py` (`list_datasets`)
- **Severity**: P1 Multi-Tenant Security
- **Symptom**: `list_datasets` bypassed tenant filtering when `principal.tenant_id == "default"`, causing authenticated HTTP callers without an explicit custom tenant to view all registered datasets across all tenants. Furthermore, server inbox files were returned globally to all callers regardless of tenant boundary.

## 2. Root Cause Analysis
- The filter condition `if principal and principal.tenant_id and principal.tenant_id != "default":` treated `"default"` as a bypass condition, exposing datasets from `tenant_a` and `tenant_b` to unprivileged callers assigned to `"default"`.
- The local server `ingest_dir` (inbox) files were listed unconditionally, exposing internal filenames and dataset metadata to remote HTTP tenants.

## 3. Resolution & Fix
- Differentiated execution principals:
  - Trusted local `stdio` (or local bootstrap) and administrators (`marketing:admin`) retain system-wide visibility into all datasets and server inbox files.
  - Remote HTTP callers (API keys, OAuth tokens) are strictly isolated to their own `tenant_id` (including `"default"`), preventing cross-tenant visibility.
  - Inbox files are only listed for trusted local `stdio` and administrators; remote non-admin tenants receive `[]`.

## 4. Verification & Prevention
- Authored `tests/security/test_tenant_isolation.py` verifying:
  - `tenant_a` callers see only their own datasets and cannot access inbox files.
  - `default` tenant callers see only `default` datasets and cannot access `tenant_a`, `tenant_b`, or inbox files.
  - Local `stdio` and admin callers can inspect all datasets and inbox files.
