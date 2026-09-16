# Failure Lesson 24: Prior Sensitivity Tool Evaluates Both Adstock and Saturation Dimensions

## 1. Executive Summary & Context
- **Component**: `src/marketing_mcp/adapters/pymc_marketing.py` (`evaluate_prior_sensitivity`)
- **Severity**: P2 Contract Fidelity & Model Risk
- **Symptom**: The tool docstring and API documentation claimed that `evaluate_prior_sensitivity` evaluates model stability under alternative adstock and saturation priors. However, the implementation only evaluated geometric/delayed adstock transformations, returning results without testing alternative saturation functions (such as Michaelis-Menten vs Logistic).

## 2. Root Cause Analysis
- The alternatives list in `evaluate_prior_sensitivity` originally contained only:
  - `shorter_memory` (adstock l_max variation)
  - `alternative_type` (geometric vs delayed adstock)
- Saturation configurations remained fixed to `base_sat_cfg`, leaving commercial sensitivity to saturation assumptions unmeasured.
- The returned dictionary lacked explicit `tested_dimensions` metadata, preventing downstream callers and autonomous agents from verifying whether both functional dimensions were tested.

## 3. Resolution & Fix
- Added alternative saturation evaluation:
  - Evaluates `michaelis_menten` vs `logistic` as an explicit third alternative scenario (`alternative_saturation`).
  - Added `dimension` tag (`"adstock"` or `"saturation"`) and explicit `scenario_config` dictionary containing both `adstock` and `saturation` keys per scenario.
  - Added `tested_dimensions: {"adstock": True, "saturation": True}` to top-level contract return payload.
  - Preserved error handling so that an error in any individual alternative scenario records `{ranks: None, error: ...}` without crashing the overall evaluation.

## 4. Verification & Prevention
- Created `tests/statistical/test_prior_sensitivity_contract.py` verifying:
  - `tested_dimensions` is `{"adstock": True, "saturation": True}`.
  - Alternatives include both adstock and saturation variations with explicit `scenario_config`.
  - Ranking shifts >= 2 positions emit `HIGH_PRIOR_SENSITIVITY` warning findings and mark `prior_stability == "sensitive"`.
  - Stable models (< 2 shifts) return `prior_stability == "robust"`.
  - Individual scenario failures are captured gracefully without unhandled exceptions.
