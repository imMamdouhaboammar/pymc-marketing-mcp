# Lesson 48: Registry Negative Guards and RFC-Gated Objective Evolution

### Context
Decision utility objective registry (`src/marketing_mcp/domain/decisions/utility.py`, `tests/unit/test_utility_objectives.py`) used by the budget optimizer.

### What happened
When planning risk-aware optimization (Candidate Gap 2), an engineer sought to register `lower_quantile` (Value-at-Risk utility). The existing unit test suite contained a protective negative guard:
```python
def test_risk_aware_objectives_not_yet_registered(self):
    """Guard: risk-aware objectives must not appear before their RFC + tests."""
    forbidden = {"cvar", "probability_exceed", "expected_regret", "lower_quantile"}
    current = set(objective_names())
    assert not current.intersection(forbidden), (
        f"Risk-aware objectives {current & forbidden} added without RFC + tests"
    )
```
The test failed immediately when `lower_quantile` was added to `_OBJECTIVE_REGISTRY` without its RFC, complete mathematical proof, and property tests.

### Observable symptom
```text
FAILED tests/unit/test_utility_objectives.py::TestObjectiveRegistry::test_risk_aware_objectives_not_yet_registered - AssertionError: Risk-aware objectives {'lower_quantile'} added without RFC + tests
```

### Impact
Prevented an incomplete or unverified objective formula from silently entering the optimizer registry where LLM agents and API callers could invoke it prematurely.

### Incorrect assumption
In many typical codebases, engineers add enum values or stub dictionary entries to registries ahead of time as "placeholders" or "TODOs". Here, doing so violates scientific integrity because LLM agents read registries dynamically and hallucinate capability readiness.

### Root cause
**Confirmed**. The project deliberately uses negative assertion guards on capability and objective registries to enforce that features cannot be registered without formal RFCs and mathematical invariant tests.

### Why the architecture allowed it
The architecture was hardened precisely to prevent speculative feature drift. The negative guard forced the implementation to follow the complete discipline:
1. Write RFC 002 (`docs/rfcs/002-risk-aware-optimization.md`) documenting Value-at-Risk mathematics and decision invariants.
2. Implement `LowerQuantileObjective` dataclass with boundary validation ($0 < \alpha < 1$).
3. Write property tests (zero-variance convergence, downside risk sensitivity, linear spend deduction, monotonicity).
4. Remove `lower_quantile` from `forbidden` in the guard test.

### Fix
Completed RFC 002, implemented `LowerQuantileObjective`, wrote 8 unit tests in `TestLowerQuantileObjective`, and updated `forbidden = {"cvar", "probability_exceed", "expected_regret"}`.

### Verification
`uv run pytest tests/unit/test_utility_objectives.py -v` passed all 23 tests, proving:
- Zero variance evaluates identically to `expected_net_profit`.
- Higher posterior spread yields strictly lower utility (risk aversion).
- Monotonicity across quantile choices: $Q_{0.10} < Q_{0.50} < Q_{0.90}$.

### Prevention rule
> **Public registries discovered by AI agents must never contain stub, placeholder, or unverified capability symbols. Enforce negative test guards (`assert not registry.intersection(unverified_symbols)`) to gate additions behind written RFCs and invariant tests.**

### Related code
- `src/marketing_mcp/domain/decisions/utility.py`
- `docs/rfcs/002-risk-aware-optimization.md`

### Related tests
- `tests/unit/test_utility_objectives.py::TestObjectiveRegistry::test_risk_aware_objectives_not_yet_registered`
- `tests/unit/test_utility_objectives.py::TestLowerQuantileObjective`

### Related lessons
- [28-statistical-authority-duplication-and-fallback-attribute-error.md](./28-statistical-authority-duplication-and-fallback-attribute-error.md)
- [39-statistical-test-assertion-drift-and-budget-conservation.md](./39-statistical-test-assertion-drift-and-budget-conservation.md)

### Status
Resolved
