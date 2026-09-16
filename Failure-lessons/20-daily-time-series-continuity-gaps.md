# Failure Lesson 20: P1 Undetected Daily Time-Series Calendar Gaps in MMM Datasets

## 1. Executive Summary & Context
- **Component**: `src/marketing_mcp/domain/datasets/validation.py`
- **Severity**: P1 Statistical Data Integrity
- **Symptom**: Ingesting a 234-day observed dataset across a 243-day calendar window passed validation without warning of the 9 missing calendar dates.

## 2. Root Cause Analysis
- `validate_mmm_dataset` checked only that total unique periods were $\ge 52$, but did not check calendar index continuity ($\Delta t$).
- In MMM, models compute Geometric/Weibull Adstock by shifting rows sequentially. When calendar dates are missing, row adjacency is falsely treated as temporal adjacency, leading to distorted decay and carryover estimates.

## 3. Resolution & Fix
- Added automatic frequency detection (daily/weekly/monthly) and calendar index diff calculation in `validate_mmm_dataset`.
- Emits structured `MISSING_PERIODS` finding containing:
  - `frequency`
  - `observed_periods`
  - `expected_periods`
  - `missing_count`
  - `first_missing_dates`

## 4. Verification & Prevention
- Verified via `tests/unit/test_wave3_fixes.py::test_validate_mmm_dataset_detects_daily_time_series_gaps` (PASS).
