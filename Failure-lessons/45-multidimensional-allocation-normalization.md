# Lesson 45: Multidimensional Allocation Normalization in Decision Service

### Context
Multidimensional panel MMM budget optimization and scenario simulation where allocations are grouped by channel and dimension cells (`dimensions`, `cells`) rather than a simple 1D channel-to-amount mapping (`dict[str, float]`).

### What happened
During the `Native Interaction Engine` CI workflow (`Statistical semantics (python)` and `Statistical semantics (rust)` jobs), `tests/statistical/test_multidimensional_pymc_sampling.py::test_real_multidimensional_mmm_panel_sampling` failed during the post-fit optimization step with:
`TypeError: '>' not supported between instances of 'list' and 'int'` at `src/marketing_mcp/services/decision_service.py:325`.

### Observable symptom
```text
Statistical semantics (python)	Run statistical decision contracts
FAILED tests/statistical/test_multidimensional_pymc_sampling.py::test_real_multidimensional_mmm_panel_sampling - TypeError: '>' not supported between instances of 'list' and 'int'
src/marketing_mcp/services/decision_service.py:325: TypeError
```

### Impact
End-to-end multidimensional MMM workflows were unable to generate economic rationales and identifiability warnings after running budget optimization, causing full workflow failure in production and CI.

### Incorrect assumption
Assumed that `allocation` returned by `optimize_budget` is always a flat dictionary of `{channel: amount}`. In multidimensional models, `allocation_from_xarray` returns `{"dimensions": dims, "cells": [{"channel": ..., "dimensions": ..., "amount": ...}]}`. Iterating over `allocation.items()` treated the top-level keys `"dimensions"` and `"cells"` as channel names, assigning `spend = cells` (a `list`), which crashed when compared against `0` in `spend_change_pct`.

### Root cause
**Confirmed**. Direct iteration over `allocation.items()` and `(baseline_allocation or {}).get(ch, 0.0)` in `DecisionService.optimize` and `DecisionService._collect_channel_identifiability_warnings` did not account for multidimensional cell-based allocation schemas.

### Why the architecture allowed it
The domain decision layer (`src/marketing_mcp/domain/decisions/allocation.py`) correctly supported multidimensional cells for optimization and simulation, but the explainability service layer (`src/marketing_mcp/services/decision_service.py`) was introduced assuming single-dimensional channel mappings without a normalization helper.

### Fix
1. Added static helper `DecisionService._channel_spend_map(allocation: dict[str, Any] | None) -> dict[str, float]` which detects cell-based structures (`cells` key) and sums amounts per channel, while passing through 1D channel-amount dictionaries.
2. Used `_channel_spend_map` in both `optimize` and `_collect_channel_identifiability_warnings` to ensure all economic rationale and identifiability checks operate on normalized channel spend numbers.
3. Added unit test `test_optimizer_handles_multidimensional_cell_allocation` in `tests/unit/test_optimizer_explainability.py`.

### Verification
1. `uv run pytest tests/unit/test_optimizer_explainability.py -v` passes cleanly (2/2 tests passed).
2. `uv run pytest tests/statistical/test_multidimensional_pymc_sampling.py -v` passes cleanly (1/1 passed).
3. `uv run ruff check .` and `uv run pyright` report 0 errors, 0 warnings.

### Prevention rule
> **Service layers consuming optimization and simulation results must never iterate over raw allocation payloads directly without running them through a dimensional normalization adapter or schema-aware visitor.**

### Related code
- `src/marketing_mcp/services/decision_service.py`
- `src/marketing_mcp/domain/decisions/allocation.py`

### Related tests
- `tests/unit/test_optimizer_explainability.py`
- `tests/statistical/test_multidimensional_pymc_sampling.py`

### Status
Resolved
