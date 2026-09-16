# Failure Lesson 28 — Statistical Authority Duplication in Native Extension & Fallback AttributeError

**Date Encountered**: 2026-09-16  
**Component**: `crates/marketing_mcp_fast/src/diagnostics.rs`, `marketing_mcp/accelerators/__init__.py`  
**Severity**: High (Violates core statistical authority invariant; silent AttributeError on fallback)  
**Impact Area**: Bayesian Decision Integrity / Native Acceleration / Fallback Reliability  

---

## 1. Executive Summary

During the architectural audit of native accelerators in `crates/marketing_mcp_fast`, two critical defects were uncovered:
1. **Statistical Policy Duplication & Inconsistency**: The native Rust module implemented its own MCMC diagnostic gatekeeper (`evaluate_mcmc_gates`) with hardcoded thresholds (`r_hat > 1.05`, `r_hat > 1.02`, `min_ess < 100`, status `"caution"`) that conflicted with the canonical Python domain diagnostics engine (`marketing_mcp.domain.diagnostics.engine.diagnose_inferencedata`) which uses richer thresholds (`r_hat > 1.01`, `min_ess < 50`, status `"approved_with_caution"`, and posterior predictive checks).
2. **Fatal Python Fallback Bug (`failures.push`)**: The pure Python fallback function `_py_fast_mcmc_diagnostics` called `failures.push(...)` (JavaScript syntax) instead of `failures.append(...)`, guaranteeing an unhandled `AttributeError: 'list' object has no attribute 'push'` whenever an unconverged model was evaluated in Python fallback mode.

---

## 2. Root Cause Analysis

### A. Architectural Authority Inversion
Native acceleration was originally introduced to speed up parsing and gate evaluations. However, by encoding business and statistical acceptance thresholds inside Rust, domain rules were duplicated across language boundaries. When the Python statistical engine evolved to include posterior predictive coverage and residual autocorrelation checks, the Rust implementation drifted.

### B. Untested Fallback Error Path
The unit tests in `test_fast_diagnostics.py` only evaluated scenarios when the native Rust extension was loaded. The Python fallback branch where `max_rhat > 1.05` was never executed under fallback conditions, concealing the invalid `.push()` call.

---

## 3. Resolution & Hardening

1. **Enforced Single Statistical Authority**:
   - Demoted native diagnostic functions to internal benchmark and comparison test utilities.
   - Declared the authoritative repository invariant: Python and established scientific packages (`PyMC`, `PyMC-Marketing`, `ArviZ`) remain the sole arbiters of model convergence and approval.
2. **Fixed Fallback Defect**:
   - Replaced `failures.push(...)` with `failures.append(...)` in `_py_fast_mcmc_diagnostics`.
   - Added regression test `test_fallback_mcmc_diagnostics_no_attribute_error` in `tests/test_rust_bridge.py` forcing Python fallback via monkeypatching.
3. **Property-Based Parity Testing**:
   - Added extensive parity tests for quantiles, LTTB compression, and sparklines covering `NaN`, `Infinity`, empty inputs, and extreme scales against NumPy.

---

## 4. Architectural Invariants Established

1. **Single Source of Truth for Scientific Policy**: Rust must never independently decide whether a Bayesian marketing model is statistically acceptable.
2. **Mandatory Fallback Parity Testing**: Every native accelerator function must have an automated test asserting 100% behavioral equivalence with its pure Python fallback under identical edge cases.
