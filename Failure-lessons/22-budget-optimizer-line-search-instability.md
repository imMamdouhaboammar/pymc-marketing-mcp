# Failure Lesson 22: P1 Budget Optimizer Line Search Instability & Multi-Start Resilience

## 1. Executive Summary & Context
- **Component**: `src/marketing_mcp/adapters/pymc_marketing.py` (`optimize_budget`)
- **Severity**: P1 Statistical Reliability
- **Symptom**: Protected statistical CI runs experienced optimizer failure in MMM budget allocation with `MinimizeException: Optimization failed: Positive directional derivative for linesearch`. The optimizer lacked a deterministic multi-start retry strategy.

## 2. Root Cause Analysis
- PyMC-Marketing's `BudgetOptimizerWrapper.optimize_budget` delegates to SciPy's `minimize(..., method="SLSQP")`.
- When initialized from default uniform budgets (`x0=None`) on complex posterior surfaces with tight tolerances (`ftol=1e-9`), numerical gradient approximations can point in a non-descent direction (`grad . p > 0`), causing SciPy's line search to terminate prematurely with a positive directional derivative exception.
- The wrapper previously executed only a single attempt, failing immediately without trying alternative deterministic starting points (historical spend, bounded midpoints) or relaxed tolerance (`ftol=1e-6`).

## 3. Resolution & Fix
- Implemented a controlled multi-start optimization loop in `PyMCMarketingAdapter.optimize_budget`:
  1. Primary attempt: default uniform initialization (`x0=None`).
  2. Alternative 1: historical baseline allocation projected onto box bounds and total budget.
  3. Alternative 2: bounded midpoint vector `(lower + upper) / 2` projected onto total budget.
  4. Alternative 3: relaxed tolerance (`ftol=1e-6, maxiter=2000`) with baseline initialization.
  5. Alternative 4: relaxed tolerance (`ftol=1e-6, maxiter=2000`) with bounded midpoint initialization.
- Added strict allocation validation: ensuring solutions satisfy box bounds (`lower - 1e-3 <= alloc <= upper + 1e-3`) and conserve total budget (`|sum - budget| <= 1e-2`).
- Enhanced return metadata with full provenance:
  - `optimizer_status: "converged"`
  - `solver: "SLSQP"`
  - `converged: True`
  - `attempts`: list of attempt logs with strategy, solver, success status, and messages
  - `attempts_count`: count of attempts executed
  - `fallback_used`: boolean indicating whether a fallback strategy was used
  - `initialization_strategy`: the winning strategy name
  - `constraint_validation`: bounds satisfaction and budget conservation audit
  - `objective_value`: scalar loss/objective value

## 4. Verification & Prevention
- Authored `tests/statistical/test_optimizer_robustness.py` asserting:
  - Line-search failure on attempt 1 triggers automatic retry on attempt 2 and converges successfully.
  - Complete failure across all strategies raises clean `DomainError("OPTIMIZATION_FAILED")`.
- Validated backward compatibility against `tests/unit/test_optimizer_failure_contract.py` (all 6 tests passing).
