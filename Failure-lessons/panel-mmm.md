# Failure Lessons: Panel MMM, Coordinate Geometry & Empirical Support

This document captures durable failure lessons, root causes, and architectural invariants for multi-region panel marketing mix models, xarray dimension preservation, and empirical support classification in `pymc-marketing-mcp`.

---

## PANEL-001: Multi-Dimensional Coordinate Reduction & Xarray Dimension Loss

### What happened
When generating response curves, plotting saturation curves, or evaluating allocations on a multi-region Panel MMM (hierarchical model across `date`, `geo`, and `channel`), the plotting and decision tools crashed with:
```text
ValueError: dimensions ('date', 'channel') do not match ('date', 'geo', 'channel')
```

### Why it mattered
* **Feature Unusable**: Panel MMM is the primary model family for enterprise advertisers operating across regional DMAs or international countries. Inability to generate plots or evaluate response curves rendered panel modeling unusable.
* **Silent Aggregation Bugs**: Earlier ad-hoc attempts to fix the crash flattened or averaged data arrays across geos before adstock transformation, mathematically corrupting regional decay dynamics.

### Observable symptom
* Unhandled `ValueError` or `KeyError: 'geo'` in plotting and response curve routines.
* Aggregation across geos yielded flattened response curves that masked regional variation.

### Initial assumption
Developers assumed that 2D single-geography MMM transformation routines could be transparently applied to panel models by looping or by relying on automatic xarray broadcasting.

### Root cause
* **Status**: Confirmed.
* Single-geography models operate on xarray DataArrays with coordinates `('date', 'channel')`. Panel models introduce the hierarchical `geo` dimension: `('date', 'geo', 'channel')`.
* Slicing and reduction operations in plotting adapters stripped the `geo` dimension or attempted to broadcast 3D arrays into 2D plotting functions expecting a scalar channel curve per timestamp.

### Why the system allowed it
Single-geography fixtures were used for the majority of plotting tests, leaving multi-dimensional panel geometries uncovered by end-to-end integration tests.

### Fix
1. **Dimension-Aware Slicing**: Refactored `PlottingService` and `PyMCMarketingAdapter` to inspect `model.coords` and dynamically handle both 2D and 3D geometries.
2. **Explicit Geo Dimension Preservation**: Preserved `(date, geo, channel)` coordinates throughout posterior extraction, downsampling, and curve generation.
3. **Geo-Specific Filtering**: Added explicit `geo: Optional[str] = None` parameters to plotting and response curve endpoints, allowing callers to evaluate specific regions or generate panel-wide faceting.

### Verification
* `tests/unit/test_hard_test_remediation.py::test_panel_mmm_coordinate_preservation_and_support_classification`
* Verified that panel models successfully generate response curves for individual geos as well as aggregated portfolios without coordinate drop or dimensionality mismatch.

### Prevention rule
> **Rule**: In multi-dimensional xarray models, dimension reductions and transformations must be explicitly coordinate-aware. Never drop or average dimensions prior to nonlinear adstock and saturation transformations.

---

## PANEL-002: Prior-Dominated Cells & Zero Empirical Spend Deception

### What happened
In a hierarchical Panel MMM with 10 regions, Channel "Billboard" had historical spend in Regions 1–9, but **exactly $0 historical spend** in Region 10 (North). When querying response curves or running budget optimization for Region 10, the platform returned a smooth, confident S-curve with positive expected sales, recommending a $50,000 spend allocation for Billboards in Region 10!

### Why it mattered
* **Dangerous Capital Reallocation**: The model recommended allocating marketing dollars to a channel in a region where it had never been tested. In real businesses, a channel might have zero spend because billboards are illegal in that region, or the company has no physical presence there.
* **The "Statistical Validity" Mirage**: Mathematically, hierarchical Bayes shrinks unobserved parameters toward the global population mean. The posterior exists and is mathematically well-defined, but it represents **100% prior belief / hierarchical borrowing** and **0% empirical observation**. Presenting this to a decision maker as an empirical finding is deceptive.

### Observable symptom
* Response curves and marginal ROAS generated for cells with zero historical data showed no visual or programmatic distinction from heavily observed cells.
* Optimizer allocated budget to unobserved channels without cautionary metadata.

### Initial assumption
"If the Bayesian posterior converged and R-hat is good, all posterior parameters are valid for decision making."

### Root cause
* **Status**: Confirmed.
* The system conflated posterior mathematical tractability with empirical data evidence:
  $$\text{Statistically Valid Posterior} \ne \text{Empirically Observed Evidence}$$
* No metadata layer existed to track historical spend support per coordinate slice `(channel, geo)`.

### Why the system allowed it
The API exposed posterior point estimates directly without inspecting the underlying dataset's empirical support geometry.

### Fix
1. **Empirical Support Classification Taxonomy**: Implemented support classification across all response curves, channel summaries, and optimization allocations:
   - `observed`: Robust historical spend ($N \ge 10$ non-zero periods) and spend variance.
   - `weak_support`: Sparse non-zero periods ($1 \le N < 10$).
   - `no_empirical_support`: Exactly zero spend in this `(channel, geo)` cell historically.
   - `extrapolated`: Evaluated spend exceeds historical maximum spend by $>20\%$.
   - `prior_dominated`: Posterior distribution is dominated by hierarchical prior shrinkage (posterior variance $\ge 90\%$ of prior variance).
2. **Actionable Decision Warnings**: When an allocation or response curve targets a `no_empirical_support` or `prior_dominated` cell, the payload includes explicit warning flags:
   ```json
   {
     "support_level": "no_empirical_support",
     "warning": "Channel 'billboard' has zero historical spend in geo 'north'. Estimate is entirely prior-dominated through hierarchical shrinkage."
   }
   ```

### Verification
* `tests/unit/test_hard_test_remediation.py::test_panel_mmm_coordinate_preservation_and_support_classification`
* `tests/unit/test_adversarial_torture_suite.py::test_zero_support_panel_detection`

### Prevention rule
> **Rule**: In hierarchical and panel models, never present prior-dominated posterior estimates as empirical evidence. Always classify and expose empirical support metadata alongside posterior predictions.

### Reusable lesson
Bayesian hierarchical models excel at borrowing strength, but decision tools must explicitly warn business users when decisions rely on shrinkage rather than observed data.

### Related failures
* [Failure Lesson 12: Saturation Curves Response Fidelity & Decision Caveats](./12-saturation-curves-response-fidelity-and-decision-caveats.md)
* `DEC-001`: SLSQP Gradient Underflow
* `statistical-workflows.md`: Statistical Workflow Contracts

---

## Protected Systems & Code References

* `src/marketing_mcp/services/plotting_service.py`: Dimension-aware curve generation and empirical support tagging
* `src/marketing_mcp/services/decision_service.py`: Support audit and warning generation in optimization
* `tests/unit/test_hard_test_remediation.py`: Panel coordinate preservation tests
* `tests/unit/test_adversarial_torture_suite.py`: Zero-support adversarial tests
