# Failure Lesson 21: P1 Deceptive Diagnostics Completed Async Checkpoint

## 1. Executive Summary & Context
- **Component**: `src/marketing_mcp/mcp/tools/jobs.py`
- **Severity**: P1 State Integrity
- **Symptom**: `submit_fit_mmm_job` recorded a progress checkpoint named `diagnostics_completed` immediately following posterior estimation, even though no diagnostics (`diagnose_mmm`) had been run.

## 2. Root Cause Analysis
- Async fitting only performs posterior sampling (`app.models.fit`), but the runner erroneously recorded `diagnostics_completed`.
- This violated server-side diagnostic decision gate invariants: downstream tooling or recovery logic could misinterpret the checkpoint as proof that convergence gates (`max_rhat`, `divergences`, `min_bfmi`) had passed.

## 3. Resolution & Fix
- Updated terminal checkpoint for fitting to `fit_completed` with 100% progress.
- Cleanly separated the model fitting stage from diagnostic evaluation.

## 4. Verification & Prevention
- Verified state transitions in `mcp/tools/jobs.py`.
