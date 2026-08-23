# Optimization & Diminishing Returns Mathematics

This guide outlines the mathematical formulation of non-linear budget optimization in PyMC-Marketing.

---

## 1. Problem Formulation

Let $K$ be the number of marketing channels, $B$ be the total available budget, and $x = [x_1, x_2, \dots, x_K]^T$ be the vector of channel spend allocations.

$$\max_{x} \quad \sum_{k=1}^K f_k(x_k)$$

Subject to:
$$\sum_{k=1}^K x_k \le B$$
$$L_k \le x_k \le U_k, \quad \forall k \in \{1, \dots, K\}$$

Where:
- $f_k(x_k)$ is the posterior expected response function for channel $k$ (integrating adstock decay and non-linear saturation).
- $L_k$ and $U_k$ are the lower and upper bounds for channel $k$.

---

## 2. Karush-Kuhn-Tucker (KKT) Optimality Conditions

Form the Lagrangian:

$$\mathcal{L}(x, \lambda, \mu, \nu) = \sum_{k=1}^K f_k(x_k) - \lambda \left(\sum_{k=1}^K x_k - B\right) + \sum_{k=1}^K \mu_k (x_k - L_k) - \sum_{k=1}^K \nu_k (x_k - U_k)$$

Stationarity condition:

$$\frac{\partial \mathcal{L}}{\partial x_k} = f'_k(x_k) - \lambda + \mu_k - \nu_k = 0$$

For any unconstrained interior channel ($L_k < x_k < U_k$, where $\mu_k = \nu_k = 0$):

$$f'_k(x_k) = \frac{\partial f_k}{\partial x_k} = \lambda$$

### The Economic Takeaway:
At optimality, the marginal return $f'_k(x_k)$ must be identical across all unconstrained channels. If Channel 1 has marginal return \$2.50 and Channel 2 has marginal return \$1.10, moving \$1 from Channel 2 to Channel 1 increases total portfolio return by $+\$1.40$.

---

## 3. Net Profit Objective Formulation

When optimizing for net profit with revenue margin $m \in (0, 1]$:

$$\max_{x} \quad \left( m \cdot \sum_{k=1}^K f_k(x_k) \right) - \sum_{k=1}^K x_k$$

The marginal condition becomes:

$$m \cdot f'_k(x_k) = 1 \implies f'_k(x_k) = \frac{1}{m}$$

If gross margin is 40% ($m = 0.40$), optimal allocation continues spending on a channel until its marginal iROAS drops to $\frac{1}{0.40} = 2.50$. Any spend beyond that yields negative net profit.
