# Optimization Mathematics & Marginal Return Theorems

This document establishes the mathematical foundations of constrained media budget allocation and dynamic flighting in PyMC-Marketing.

---

## 1. The Multi-Channel Allocation Problem

Let $K$ be the number of media channels, $B$ be the total available budget, and $f_k(x_k)$ be the Bayesian posterior expectation of the saturation response function for channel $k$.

$$\max_{x_1, \dots, x_K} \sum_{k=1}^K f_k(x_k)$$
subject to:
$$\sum_{k=1}^K x_k = B, \quad L_k \le x_k \le U_k \quad \forall k \in \{1, \dots, K\}$$

### Karush-Kuhn-Tucker (KKT) Optimality Conditions:
At the optimal allocation $x^*$, the Lagrangian is:
$$\mathcal{L}(x, \lambda, \mu_L, \mu_U) = \sum_{k=1}^K f_k(x_k) - \lambda \left( \sum_{k=1}^K x_k - B \right) + \sum_{k=1}^K \mu_{L, k}(x_k - L_k) + \sum_{k=1}^K \mu_{U, k}(U_k - x_k)$$

For all channels strictly inside their bounds ($L_k < x_k^* < U_k$), the marginal returns are equal:
$$f_1'(x_1^*) = f_2'(x_2^*) = \dots = f_m'(x_m^*) = \lambda$$

---

## 2. Marginal iROAS vs Total iROAS

- **Total iROAS**: Average return across all historical spend:
  $$\text{Total iROAS}_k = \frac{f_k(x_k)}{x_k}$$
- **Marginal iROAS**: Instantaneous derivative representing the incremental return of the next dollar:
  $$\text{Marginal iROAS}_k = \left.\frac{d f_k}{d x}\right|_{x = x_k}$$

Because saturation curves are concave ($f''(x) < 0$), Total iROAS is always strictly greater than Marginal iROAS for non-zero spend. Allocating budget by Total iROAS over-allocates to saturated channels.

---

## 3. Extrapolation Risk Boundary

When a proposed allocation $x_k$ satisfies:
$$x_k > 1.5 \times \text{Quantile}_{0.95}(\text{Historical Spend}_k)$$
The evaluation region lies outside empirical support. In PyMC-Marketing, posterior predictive variance widens exponentially:
$$\text{Var}(f_k(x_k) \mid \mathcal{D}) \gg \text{Var}(f_k(x_{\text{obs}}) \mid \mathcal{D})$$
The system flags `EXTRAPOLATION_RISK` and recommends boundary testing.
