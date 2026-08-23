# Information Criteria & Model Selection Guide

This guide covers out-of-sample predictive accuracy assessment, PSIS-LOO cross-validation, WAIC, and Bayesian Model Averaging (BMA) stacking in PyMC-Marketing.

---

## 1. Expected Log Pointwise Predictive Density ($\text{elpd}$)

To compare competing models without overfitting historical in-sample data, we estimate out-of-sample predictive density using Leave-One-Out Cross-Validation ($\text{elpd}_{\text{loo}}$).

$$\text{elpd}_{\text{loo}} = \sum_{i=1}^n \log p(y_i \mid y_{-i})$$

---

## 2. PSIS-LOO & Pareto $k$ Diagnostic

Calculating exact leave-one-out CV requires fitting $n$ models. Pareto Smoothed Importance Sampling (PSIS) approximates this from a single model fit by re-weighting posterior draws.

### The Pareto $k$ Diagnostic Scale:
- **$k \le 0.5$ (Good)**: The importance weights have finite variance; the LOO estimate is extremely reliable.
- **$0.5 < k \le 0.7$ (OK)**: Practical convergence is acceptable, though variance is slightly elevated.
- **$k > 0.7$ (Unreliable / Bad)**: The importance sampling distribution has infinite variance. The LOO estimate is untrustworthy for this observation, indicating an extreme outlier or severe model misspecification.

When `select_best_model` reports $k > 0.7$, the agent must inspect the observation dates to see if unmodeled external shocks (e.g. site outage, Black Friday spike) occurred.

---

## 3. Stacking & Bayesian Model Averaging (BMA)

Rather than picking a single "winner" and discarding all other hypotheses, **Bayesian Model Stacking** finds a convex combination of model predictions:

$$\hat{y}_{\text{stack}} = \sum_{m=1}^M w_m \hat{y}^{(m)}, \quad \text{where } \sum w_m = 1, \quad w_m \ge 0$$

The weights $w_m$ are optimized to maximize the combined leave-one-out log scoring rule.

### Practical Agent Usage:
- If `select_best_model` returns weights `{"mmm_geometric": 0.65, "mmm_delayed": 0.35}`, it indicates that a mixture of immediate and delayed decay dynamics best describes the empirical data.
- The agent should explain both perspectives in the final summary.
