# Optimization Mathematics & Marginal Return Principles

This document details the mathematical foundations of constrained media budget allocation in PyMC-Marketing.

---

## 1. The Multi-Channel Allocation Problem

Let $K$ be the number of media channels, $B$ be the total available budget, and $f_k(x_k)$ be the posterior expectation of the saturation response function for channel $k$:

$$\max_{x_1, \dots, x_K} \sum_{k=1}^K f_k(x_k)$$
subject to:
$$\sum_{k=1}^K x_k = B, \quad L_k \le x_k \le U_k \quad \forall k \in \{1, \dots, K\}$$

### Optimality Conditions (KKT):
For all channels strictly inside their bounds ($L_k < x_k^* < U_k$), optimal allocation balances marginal returns:
$$f_1'(x_1^*) = f_2'(x_2^*) = \dots = f_m'(x_m^*) = \lambda$$

---

## 2. Marginal iROAS vs Total iROAS

- **Total iROAS**: Average return across total spend:
  $$\text{Total iROAS}_k = \frac{f_k(x_k)}{x_k}$$
- **Marginal iROAS**: Derivative representing the return of the next dollar:
  $$\text{Marginal iROAS}_k = \left.\frac{d f_k}{d x}\right|_{x = x_k}$$

Under concave saturation ($f''(x) < 0$), Total iROAS exceeds Marginal iROAS for non-zero spend. Allocating budget based on historical Total iROAS over-allocates capital to saturated channels.

---

## 3. Extrapolation Risk Boundary

When a proposed allocation $x_k$ exceeds historical boundaries:
$$x_k > 1.5 \times \text{Quantile}_{0.95}(\text{Historical Spend}_k)$$
The evaluation region lies outside observed data support, widening posterior predictive variance. The system flags `EXTRAPOLATION_RISK`.
