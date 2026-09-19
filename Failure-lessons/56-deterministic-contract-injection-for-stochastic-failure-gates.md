# Lesson 56: Deterministic Contract Injection for Stochastic Failure Gates

### Context
Statistical MCMC diagnostics and decision gating (`tests/contract/test_decision_gates_contract.py`, `src/marketing_mcp/services/decision_service.py`).

### What happened
Tests asserting that decision gates block optimization when models fail diagnostics (`validation_state="rejected"`) initially relied on running short MCMC sampling fits with bad priors or adversarial data, hoping sampling would produce high R-hat or divergences. In CI, stochastic sampling on different CPU architectures occasionally converged well enough to avoid triggering diagnostic thresholds, causing flaky test runs.

### Observable symptom
Flaky CI test failures in stochastic decision tests:
```text
AssertionError: Expected GATE_DECISION_BLOCKED, got GATE_DECISION_PASSED (rhat=1.02, divergences=0)
```
Tests would pass on macOS ARM64 machines but fail intermittently on Linux x86_64 CI runners due to slight differences in OpenBLAS / PyTensor linear algebra numerical stability.

### Impact
- **CI Flakiness & Velocity Drag**: Intermittent test failures stalled development branches and generated false alarms.
- **Verification Uncertainty**: Falsification and gate enforcement tests were not guaranteed to exercise the rejection path on every execution.

### Incorrect assumption
Assumed that statistical stochasticity could reliably simulate hard failure states across different hardware, thread counts, and BLAS libraries.

### Root cause
**Confirmed**.
Conflating *statistical engine verification* (does MCMC produce divergences on bad data?) with *governance contract verification* (does the decision gate block when validation status is rejected?).

### Why the architecture allowed it
Contract tests used end-to-end sampling execution rather than directly asserting gate behavior against seeded or mocked model metadata states.

### Fix
1. Authored `tests/contract/test_decision_gates_contract.py` with deterministic diagnostic injection:
Directly seeded the model repository with an immutable model artifact containing explicit failure diagnostics (`max_rhat=1.35`, `divergences=12`, `failures=["high_rhat", "divergences"]`), verifying that `DecisionService.optimize` and `DecisionService.allocate` fail closed deterministically in 0ms.
2. For end-to-end integration tests (`test_analyst_journey_e2e.py`), tuned MCMC sampling parameters (`tune=1000`, `target_accept=0.9`) so that legitimate pipeline tests consistently converge cleanly without stochastic divergence spikes.

### Verification
- `tests/contract/test_decision_gates_contract.py::test_decision_gate_blocks_rejected_model_contract` (deterministic, 0ms execution)
- `tests/integration/test_analyst_journey_e2e.py` (passes 100% reliably across 10 consecutive local and CI executions)

### Prevention rule
> **Never rely on stochastic sampling to trigger safety and decision gates in contract tests; always verify governance policies against deterministic injected failure payloads.**

### Reusable lesson
Separate statistical correctness testing from policy enforcement testing. Policy gates must be tested with deterministic fixtures, leaving statistical bounds to dedicated, controlled statistical suites.

### Related code
- `src/marketing_mcp/services/decision_service.py`
- `src/marketing_mcp/services/diagnostics.py`

### Related tests
- `tests/contract/test_decision_gates_contract.py`
- `tests/integration/test_analyst_journey_e2e.py`

### Status
Solved (commits `cfc3612` and `284afa0`, merged in `69f6280`)
