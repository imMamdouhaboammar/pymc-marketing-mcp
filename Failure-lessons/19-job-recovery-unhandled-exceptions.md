# Failure Lesson 19: P1 Job Recovery NameError & Raw ValueError Exposure

## 1. Executive Summary & Context
- **Component**: `src/marketing_mcp/jobs/service.py`, `src/marketing_mcp/mcp/tools/jobs.py`
- **Severity**: P1 API Reliability (Unhandled Server Crashes)
- **Symptom**: Calling `resume_job()` on an invalid or un-resumable job threw an unhandled `NameError: name 'DomainError' is not defined`. Calling `list_jobs(status="banana")` threw an unhandled `ValueError`.

## 2. Root Cause Analysis
1. `JobService` imported various models and repositories but forgot `from marketing_mcp.errors import DomainError`.
2. `list_jobs` converted the incoming string directly via `JobStatus(status)` without catching `ValueError`.

## 3. Resolution & Fix
- Added `DomainError` import to `jobs/service.py`.
- Wrapped `JobStatus` conversion in `tools/jobs.py` with case-normalization and clear `DomainError("INPUT_INVALID")` detailing allowed statuses.

## 4. Verification & Prevention
- Verified via `tests/unit/test_wave2_fixes.py::test_job_service_resilience_and_imports` (PASS).
