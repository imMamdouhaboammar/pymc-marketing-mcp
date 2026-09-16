# Failure Lesson 25: Remote Dataset Content-Type Verification & Temporal Period Summaries

## 1. Executive Summary & Context
- **Component**: `src/marketing_mcp/mcp/tools/datasets.py`, `src/marketing_mcp/services/dataset_service.py`, `src/marketing_mcp/domain/datasets/validation.py`, `src/marketing_mcp/schemas/models.py`
- **Severity**: P2 Ingestion Security & Data Integrity
- **Symptom**: Remote URL dataset registration accepted arbitrary HTTP Content-Types (such as `text/html`, `application/json`, or binary blobs), leading to silent parsing errors or unhandled exceptions in pandas. Additionally, dataset validation reports did not summarize observed vs. expected calendar periods or quantify missing time periods.

## 2. Root Cause Analysis
- `register_dataset` from URL checked neither the response `Content-Type` header nor the payload signature, allowing HTML 404/login pages or arbitrary text to be stored as datasets.
- `register_bytes` parsed data with `read_tabular_bytes` without sniffing whether the content was actually tabular CSV/TSV/Parquet versus HTML or JSON.
- `DatasetValidationResult` in `schemas/models.py` lacked a `temporal_summary` field, forcing callers and agents to parse unstructured warning messages to determine how many periods were missing in time series data.

## 3. Resolution & Fix
- Added Content-Type validation in `src/marketing_mcp/mcp/tools/datasets.py`:
  - Enforces `text/csv`, `text/plain`, `text/tab-separated-values`, `application/octet-stream`, `application/vnd.apache.parquet`.
  - Rejects `text/html`, `application/json`, and XML with `DomainError("INVALID_REMOTE_DATASET")`.
- Added byte sniffing in `src/marketing_mcp/services/dataset_service.py` (`register_bytes`):
  - Rejects payloads starting with HTML/XML markers (`<!doctype`, `<html`, `<?xml`) or JSON markers (`{"`, `[{`).
  - Verifies that tabular datasets contain more than one column.
- Added `temporal_summary` to `DatasetValidationResult` schema and `app.datasets.validate`:
  - Contains `frequency`, `observed_periods`, `expected_periods`, `missing_period_count`.
  - Surfaced in both validation summary and error evidence for `validate_dataset`.

## 4. Verification & Prevention
- Authored `tests/security/test_dataset_content_verification.py` verifying:
  - Remote URLs serving HTML or JSON are rejected with `INVALID_REMOTE_DATASET`.
  - Byte registration of HTML or JSON is rejected with `INVALID_DATASET_CONTENT`.
- Authored `tests/unit/test_wave3_fixes.py` verifying:
  - Gapped time series emit `MISSING_PERIODS` and include full `temporal_summary` with exact observed vs. expected period counts.
