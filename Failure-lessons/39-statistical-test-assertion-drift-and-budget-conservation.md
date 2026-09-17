# Lesson 39: Statistical Test Assertion Drift & Budget Conservation

### Context
Statistical decision invariant testing in `tests/statistical/test_decision_invariants.py`.

### What happened
`test_flighting_respects_conservation_floors_and_caps` asserted that all channel allocations satisfied `min(weeks) >= 200.0`, even though the test's own input constraints specified `min_weekly=150.0` for `meta` and `min_weekly=100.0` for `google`. Furthermore, total budget conservation was calculated as `total = ...` but was never asserted.

### Observable symptom
Pytest failed with `AssertionError: meta min bound: 150.0 >= 200.0`, and Ruff flagged `F841 Local variable total is assigned to but never used`.

### Impact
Falsely failed a valid statistical optimizer and allowed regressions in budget conservation to go undetected because the assertion was never executed.

### Incorrect assumption
The test author assumed arbitrary constant thresholds rather than asserting domain invariants derived from input parameters.

### Root cause
**Confirmed**. Test assertions drifted from test inputs during refactoring, and an intended invariant check (`total == 8000.0`) was left as an unasserted variable assignment.

### Why the architecture allowed it
Test code was not audited with linters enforcing unused variable detection (`F841`), allowing unasserted calculations to silently pass without warning.

### Fix
Aligned assertions with input parameters (`min(meta_weeks) >= 149.99`, `max(meta_weeks) <= 700.01`, `min(google_weeks) >= 99.99`, `max(google_weeks) <= 900.01`) and added the missing budget conservation assertion `assert abs(total - 8000.0) < 5.0`.

### Verification
`tests/statistical/test_decision_invariants.py` passes all 6 tests in 31.13s; Ruff confirms zero unused variable warnings.

### Prevention rule
> **Statistical tests must assert domain invariants (conservation of mass/budget, constraint satisfaction, monotonicity) relative to their input parameters, and linters must strictly flag unused variables to prevent phantom assertions.**

### Reusable lesson
When a test computes a metric without asserting it, treat it as a critical test defect (a "phantom test"). Linters must run on tests as strictly as on source code.

### Related code
- `tests/statistical/test_decision_invariants.py`
- `src/marketing_mcp/domain/decisions/flighting.py`

### Related tests
- `tests/statistical/test_decision_invariants.py::test_flighting_respects_conservation_floors_and_caps`

### Related lessons
- [22-budget-optimizer-line-search-instability.md](./22-budget-optimizer-line-search-instability.md)
- [26-adversarial-harsh-regression-matrix.md](./26-adversarial-harsh-regression-matrix.md)
- [testing-and-verification.md](./testing-and-verification.md)

### Status
Resolved
