# Buy-'Til-You-Drop (BTYD) Mathematics Guide

This guide details the mathematical foundations of the BG/NBD and Gamma-Gamma models in PyMC-Marketing.

---

## 1. The BG/NBD Model

The Beta-Geometric / Negative Binomial Distribution (BG/NBD) model governs non-contractual repeat purchase behavior.

### Assumptions:
1. While active, customer $i$ makes purchases according to a Poisson process with transaction rate $\lambda_i$:
   $$P(X(t) = x \mid \lambda_i) = \frac{(\lambda_i t)^x e^{-\lambda_i t}}{x!}$$
2. Heterogeneity in $\lambda_i$ follows a Gamma distribution:
   $$\lambda_i \sim \text{Gamma}(r, \alpha)$$
3. After any transaction, customer $i$ becomes inactive with probability $p_i$.
4. Heterogeneity in $p_i$ follows a Beta distribution:
   $$p_i \sim \text{Beta}(a, b)$$

### Probability of Being Active $P(\text{alive})$:
$$P(\text{alive} \mid x, t_x, T, r, \alpha, a, b) = \frac{1}{1 + \frac{a}{b + x} \left( \frac{\alpha + T}{\alpha + t_x} \right)^{r + x}}$$

---

## 2. The Gamma-Gamma Spend Model

Models average transaction monetary value $m_x$ across $x$ repeat transactions.

### Assumptions:
1. Customer $i$'s transaction value $v$ follows a Gamma distribution with mean $\mathbb{E}[V] = \nu_i / p$.
2. Heterogeneity in $\nu_i$ across customers follows a Gamma distribution:
   $$\nu_i \sim \text{Gamma}(q, \gamma)$$
3. **Core Assumption**: Monetary value is independent of transaction frequency.

---

## 3. Discounted Customer Lifetime Value

$$\text{CLV}(t, d) = \sum_{k=1}^t \frac{\mathbb{E}[X(k) - X(k-1)] \cdot \mathbb{E}[M]}{(1 + d)^k}$$
where $d$ is the period discount rate.
