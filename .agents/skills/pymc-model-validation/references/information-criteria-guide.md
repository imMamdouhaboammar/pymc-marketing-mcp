# Information Criteria & Bayesian Model Comparison Guide

When multiple model specifications are evaluated, PyMC-Marketing provides information-theoretic model comparison via ArviZ.

---

## 1. PSIS-LOO (Pareto Smoothed Importance Sampling LOO)

PSIS-LOO approximates Leave-One-Out cross-validation without refitting the model $N$ times:
$$\text{elpd}_{\text{loo}} = \sum_{i=1}^n \ln p(y_i \mid y_{-i})$$

### Pareto $k$ Diagnostic:
Importance weights are fitted with a generalized Pareto distribution:
- **$k \le 0.5$**: Excellent reliability.
- **$0.5 < k \le 0.7$**: Good / acceptable reliability.
- **$k > 0.7$**: Unreliable. The posterior is sensitive to individual observation $i$.

---

## 2. WAIC (Widely Applicable Information Criterion)

$$\text{WAIC} = -2 \left( \text{lppd} - p_{\text{waic}} \right)$$
WAIC provides an asymptotic approximation to out-of-sample predictive accuracy. LOO is generally preferred over WAIC due to superior diagnostic capabilities via Pareto $k$.

---

## 3. Bayesian Model Stacking

Rather than picking a single winner, stacking finds optimal weights $w_k$ (with $\sum w_k = 1$) that maximize leave-one-out log score:
$$\max_{w} \sum_{i=1}^N \ln \left( \sum_{k=1}^K w_k \, p(y_i \mid y_{-i}, M_k) \right)$$

---

## 4. Comparison Invariant

Models being compared must share the same underlying dataset and compatible target definitions (`same_dataset_comparison` gate). Comparing models trained on different subsets or transformations of $y$ without Jacobian adjustment is statistically invalid.
