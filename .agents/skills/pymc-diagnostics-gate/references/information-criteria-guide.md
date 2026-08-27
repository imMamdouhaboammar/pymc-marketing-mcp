# Information Criteria & Bayesian Model Comparison Guide

When multiple model specifications are plausible, PyMC-Marketing provides information-theoretic model comparison via ArviZ.

---

## 1. PSIS-LOO (Pareto Smoothed Importance Sampling LOO)

PSIS-LOO approximates exact Leave-One-Out cross-validation without refitting the model $N$ times:
$$\text{elpd}_{\text{loo}} = \sum_{i=1}^n \ln p(y_i \mid y_{-i})$$

### Pareto $k$ Diagnostic:
The importance weights $w_i = 1 / p(y_i \mid \theta)$ are fitted with a generalized Pareto distribution.
- **$k \le 0.5$**: Excellent importance sampling reliability.
- **$0.5 < k \le 0.7$**: Good / acceptable reliability.
- **$k > 0.7$**: Unreliable. The posterior is sensitive to observation $i$. PyMC-Marketing flags these observations.

---

## 2. WAIC (Widely Applicable Information Criterion)

$$\text{WAIC} = -2 \left( \text{lppd} - p_{\text{waic}} \right)$$
WAIC provides an asymptotic approximation to out-of-sample predictive accuracy. LOO is generally preferred over WAIC due to superior diagnostic capabilities via Pareto $k$.

---

## 3. Bayesian Model Stacking

Rather than selecting a single "winner", Bayesian stacking finds optimal convex combination weights $w = (w_1, \dots, w_K)$ with $\sum w_k = 1$ that maximize leave-one-out log score:
$$\max_{w} \sum_{i=1}^N \ln \left( \sum_{k=1}^K w_k \, p(y_i \mid y_{-i}, M_k) \right)$$

### Interpreting Stacking Weights:
| Model ID | Transform Specification | $\Delta \text{elpd}_{\text{loo}}$ | Weight $w_k$ | Interpretation |
|---|---|---|---|---|
| `mmm_v2_delayed` | Delayed adstock + Hill saturation | 0.0 | 0.72 | Primary model; receives 72% predictive weight. |
| `mmm_v1_geom` | Geometric adstock + Logistic sat | -12.4 | 0.28 | Complementary; captures short-term dynamics. |
| `mmm_v3_weibull` | Weibull adstock + Tanh sat | -45.8 | 0.00 | Over-parameterized; zero stacking contribution. |
