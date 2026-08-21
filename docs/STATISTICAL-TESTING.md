# Statistical Testing Methodology

Testing Bayesian Marketing Mix Models requires a different paradigm than deterministic software testing. This document describes the statistical invariant testing framework used in PyMC Marketing MCP.

## 1. Principle of Invariant Testing

Because MCMC sampling is inherently stochastic, tests must NEVER assert exact floating-point equality for posterior samples. Instead, tests assert mathematical and statistical invariants:

1. **Finite Quantities**: All posterior medians, credible intervals, standard deviations, and likelihood terms must be finite real numbers (`np.isfinite`).
2. **Interval Consistency**: The lower bound of a credible interval must strictly not exceed the median, and the median must not exceed the upper bound:
   $$ \text{lower}_{94\%} \le \text{median} \le \text{upper}_{94\%} $$
3. **Probability Bounds**: Probability metrics such as $P(\text{iROAS} > 1)$ or $P(\text{Scenario} > \text{Baseline})$ must strictly lie in $[0.0, 1.0]$.
4. **Diminishing Returns (Saturated Channels)**: Due to concave saturation curves (logistic/Michaelis-Menten), marginal iROAS at current or higher spend must not exceed initial low-spend returns, establishing a clear distinction between Total iROAS and Marginal iROAS.
5. **Budget Conservation**: Optimized budget allocations across channels or cells must sum to the specified total budget within numerical tolerance ($10^{-3}$).
6. **Constraint Satisfaction**: Every recommended channel or cell allocation must satisfy $x_i \in [\min_i, \max_i]$.

## 2. Test Execution Profiles

| Profile | Sampler Configuration | Typical Runtime | Usage |
| :--- | :--- | :--- | :--- |
| **Smoke Profile (CI)** | `draws=200, tune=200, chains=2` | ~4 seconds per fit | Fast automated regression checking with `pytest -n auto` |
| **Validation Profile** | `draws=1000, tune=1000, chains=4` | ~25 seconds per fit | Production verification, R-hat <= 1.01 validation |

## 3. Synthetic Data Generation

The test suite relies on `marketing_mcp.demo_data` to generate reproducible synthetic datasets with known data-generating processes (DGP):
- **Single-dimensional MMM**: 104 weeks with known ground-truth contributions for Meta, Google, TikTok, and YouTube.
- **Multidimensional Panel MMM**: Rectangular panel across Saudi cities (`Riyadh`, `Jeddah`, `Dammam`) with cell-specific adstock decay and saturation scales.
- **Experimental Lift Tests**: Ground-truth synthetic incremental lift measurements with known standard errors ($\sigma$).
