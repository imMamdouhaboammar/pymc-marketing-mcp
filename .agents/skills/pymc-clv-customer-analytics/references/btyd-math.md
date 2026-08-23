# Buy-'Til-You-Drop (BTYD) Mathematics Guide

Mathematical formulations for BG/NBD, Gamma-Gamma, and Shifted Beta-Geometric models.

---

## 1. BG/NBD Model (Beta-Geometric / Negative Binomial Distribution)

### Assumptions:
1. Active customer transaction count follows $\text{Poisson}(\lambda t)$.
2. Transaction rate $\lambda$ across customers follows $\text{Gamma}(r, \alpha)$.
3. After any transaction, a customer churns with probability $p$.
4. Dropout probability $p$ across customers follows $\text{Beta}(a, b)$.

### Probability of Being Alive:

$$P(\text{Alive} \mid x, t_x, T, r, \alpha, a, b) = \frac{1}{1 + \frac{a}{b + x - 1} \left( \frac{\alpha + T}{\alpha + t_x} \right)^{r + x}}$$

Where:
- $x$: number of repeat transactions
- $t_x$: recency (time of last transaction)
- $T$: total observation time

---

## 2. Gamma-Gamma Model (Monetary Value)

Estimates customer expected transaction value $E(M)$, independent of transaction frequency.

### Assumptions:
1. Transaction value $z_i$ follows $\text{Gamma}(p, \nu)$.
2. Average monetary value parameter $\nu$ follows $\text{Gamma}(q, \gamma)$.

### Expected Monetary Value per Transaction:

$$E(M \mid p, q, \gamma, m_x, x) = \frac{\gamma + m_x x}{p x + q - 1} \cdot p$$

---

## 3. Shifted Beta-Geometric (sBG) Model (Contractual)

Models discrete subscription renewal/churn rates across billing cycles ($t = 1, 2, \dots$).

$$\theta \sim \text{Beta}(\alpha, \beta)$$
$$P(T = t \mid \theta) = \theta (1 - \theta)^{t-1}$$
