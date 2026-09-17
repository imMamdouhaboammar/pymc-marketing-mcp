# Failure Lessons: Decision Integrity & Economic Optimization

This document captures durable failure lessons, root causes, and architectural invariants for marketing decision engines, budget allocation, and flighting optimization in `pymc-marketing-mcp`.

---

## DEC-001: SLSQP Gradient Underflow on High-Budget Flighting Optimization

### What happened
When optimizing multi-period budget flighting over an 8-week horizon with a large total budget ($10,000,000) across 4 marketing channels, `optimize_flighting` returned an exactly flat 25% equal allocation across all channels ($312,500 per channel per week for all 8 weeks). It completely ignored distinct channel saturation curves, adstock decays, and historical response curves.

### Why it mattered
* **Business & Capital Allocation Impact**: In real-world enterprise deployments, recommending uniform spend allocation directly misallocates millions of dollars into low-ROI or saturated channels.
* **Deceptive Correctness**: The optimizer terminated with `success: True` and `status: "converged"`. Plausible-looking optimization outputs are far more dangerous than exceptions because callers (and autonomous AI agents) have no immediate indication of failure.

### Observable symptom
* Optimization on synthetic datasets with known asymmetric returns (Channel 1 having $3\times$ higher return than Channel 4) produced identical allocations across all channels.
* Spend schedule was identical to the initial starting point vector $x_0 = \frac{B}{T \cdot C}$.
* Gradient norm reported in solver iterations was $0.0$.

### Initial assumption
The implementation assumed that SciPy's `minimize(..., method="SLSQP")` with numerical finite-difference gradient approximation would scale smoothly when decision variables represented raw dollar values $x_{t, c} \in [0, 10^7]$.

### Root cause
* **Status**: Confirmed.
* SciPy's finite-difference approximation computes directional gradients via:
  $$\nabla f_i(x) \approx \frac{f(x + \epsilon \cdot e_i) - f(x)}{\epsilon}$$
* In default SciPy SLSQP, $\epsilon \approx \sqrt{\epsilon_{\text{mach}}} \approx 1.49 \times 10^{-8}$.
* When $x_i \approx 10^6 - 10^7$, the perturbation $x_i + \epsilon$ in IEEE 754 float64 arithmetic underflows:
  $$10,000,000.0 + 0.0000000149 = 10,000,000.0$$
* Because the perturbed input evaluated to the exact same float64 bit pattern, $f(x + \epsilon) - f(x) \equiv 0.0$, yielding a zero gradient $\nabla f = 0$. The line-search algorithm determined that no step could improve the objective and terminated at iteration 0, declaring victory on the uniform initial guess.

### Why the system allowed it
1. `optimize_flighting` was implemented as a standalone numerical procedure rather than inheriting the normalized parameterization used by battle-tested budget allocators.
2. Initial unit tests only asserted structural invariants (`len(schedule) == 8` and `sum(schedule) == budget`), creating the illusion of verified functionality without checking economic sensitivity.

### Fix
1. **Normalized Simplex Parameterization**: Transformed decision variables from raw currency units $x_{t,c}$ to budget fractions $w_{t,c} \in [0, 1]$ constrained to the unit simplex:
   $$\sum_{t=1}^T \sum_{c=1}^C w_{t,c} = 1.0, \quad x_{t,c} = w_{t,c} \cdot B_{\text{total}}$$
2. **Scale-Invariant Gradient Step**: Configured finite differences with scale-appropriate relative step sizes ($\epsilon = 10^{-5}$) on the normalized domain.
3. **Objective Normalization**: Scaled objective loss values by estimated baseline sales so that gradients remain $O(1)$.
4. **Deterministic Multi-Start Strategy**: Implemented fallback restarts (historical baseline allocation, bounded midpoints, perturbed starts) if the primary search stagnates.

### Verification
* `tests/statistical/test_flighting_optimization.py::test_flighting_optimizer_gradient_underflow_prevention`
* `tests/statistical/test_flighting_optimization.py::test_flighting_optimizer_asymmetric_allocation_on_high_budget`
* Verified that on a $10M budget with asymmetric channel returns, the high-return channel receives $>40\%$ of total budget while the low-return channel receives $<15\%$, with solver iterations $>10$.

### Prevention rule
> **Rule**: Never execute numerical gradient optimization directly over unscaled monetary variables. Always optimize over normalized unit simplexes ($w \in [0, 1]$ with $\sum w = 1$) with scale-invariant finite-difference steps.

### Reusable lesson
Numerical optimization routines are scale-sensitive. Plausible outputs that match constraints are not proof of convergence. Always test optimization algorithms against known asymmetric ground-truth fixtures and extreme scale ranges ($10^2$ to $10^8$).

### Related failures
* [Failure Lesson 22: Budget Optimizer Line Search Instability](./22-budget-optimizer-line-search-instability.md)
* `DEC-002`: Target Scale Divergence Between Decision Paths

---

## DEC-002: Target Scale Divergence Between Flighting and Allocation Decision Paths

### What happened
Evaluating the exact same fitted MMM model produced radically divergent sales estimates across two decision endpoints:
* `optimize_budget` predicted **~450,000** incremental sales for a $100k budget.
* `optimize_flighting` predicted **~1.59** incremental sales for the identical budget and model.

### Why it mattered
* A 5-orders-of-magnitude discrepancy destroys platform trust.
* ROI metrics and cost-per-acquisition (CPA) calculations derived from flighting outputs were completely inverted, indicating marketing campaigns were catastrophic failures when they were highly profitable.

### Observable symptom
* Flighting outputs reported total expected sales in single digits ($O(1)$) while budget optimization reported hundreds of thousands of sales ($O(10^5)$).

### Initial assumption
Developers assumed that evaluating the PyMC-Marketing model's underlying PyTensor computational graph directly yielded predictions in original target units.

### Root cause
* **Status**: Confirmed.
* PyMC-Marketing normalizes target data (e.g., using `MaxAbsScaler` or `StandardScaler`) prior to MCMC sampling to ensure numerical stability during NUTS sampling.
* The model object stores target scale parameters in its coordinates or attributes (e.g. `model.target_scale` or `model.y_scaler`).
* While `optimize_budget` wrapped evaluation through PyMC-Marketing's internal `BudgetOptimizerWrapper` which automatically multiplies graph outputs by `target_scale`, `optimize_flighting` evaluated the raw PyTensor function directly without applying the inverse transformation.

### Why the system allowed it
The platform maintained two divergent response-evaluation code paths: one delegating to PyMC-Marketing's wrapper, and one custom-coded for multi-period flighting.

### Fix
1. Unified response evaluation in `PyMCMarketingAdapter.evaluate_flighting_response` and `FlightingDomainOptimizer`.
2. Inspect target transformation metadata via `getattr(model, "target_scale", 1.0)` and model coordinate metadata.
3. Apply inverse scaling to all evaluated posterior points before computing loss or returning expected response metrics.

### Verification
* `tests/unit/test_hard_test_remediation.py::test_flighting_response_scaling_matches_target_scale`
* Asserts that `evaluate_flighting_response` scales output by exactly `target_scale` relative to the raw PyTensor graph evaluation.

### Prevention rule
> **Rule**: Decision endpoints that represent the same economic model must share one canonical response-evaluation path. Any model with normalized targets must encapsulate inverse scaling within its public evaluation API.

### Reusable lesson
When a model framework normalizes inputs or targets, verify that every downstream consumer (inference, response curves, scenario planning, optimization) goes through a centralized de-normalization adapter.

### Related failures
* `DEC-001`: SLSQP Gradient Underflow
* `PANEL-001`: Coordinate Aggregation & Empirical Support

---

## Protected Systems & Code References

* `src/marketing_mcp/domain/decisions/flighting.py`: [`FlightingDomainOptimizer`](file:///Users/mamdouhaboammar/Documents/pymc-unified-platform-spec/pymc-marketing-mcp/src/marketing_mcp/domain/decisions/flighting.py)
* `src/marketing_mcp/adapters/pymc_marketing.py`: [`PyMCMarketingAdapter.evaluate_flighting_response`](file:///Users/mamdouhaboammar/Documents/pymc-unified-platform-spec/pymc-marketing-mcp/src/marketing_mcp/adapters/pymc_marketing.py)
* `tests/statistical/test_flighting_optimization.py`: Statistical verification under real NUTS MCMC posteriors
* `tests/unit/test_flighting_domain.py`: 21 domain invariant unit tests
