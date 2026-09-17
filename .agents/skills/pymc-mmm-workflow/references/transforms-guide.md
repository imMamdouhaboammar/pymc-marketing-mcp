# Adstock and Saturation Transforms Guide

This guide details the mathematical foundations, parameter interpretations, and practical selection rules for media transformation functions available in PyMC-Marketing.

---

## 1. Adstock Transformations (Carryover / Memory)

Adstock models the delayed and decaying effect of advertising impressions or spend over time. Parameters are estimated from data through prior distributions, not assumed as fixed constants.

### A. Geometric Adstock (`type: "geometric"`)

The classical Koyck transformation. Each period's effective adstock is a weighted decay of prior spend.

$$\text{Adstock}_t = x_t + \alpha \cdot \text{Adstock}_{t-1}$$

- **Parameters**:
  - `alpha` ($\alpha \in [0, 1)$): Retention rate. Estimated via prior (e.g. Beta prior).
  - `l_max`: Maximum lag window computed.
- **Half-Life Formula**:
  $$t_{1/2} = \frac{-\ln(2)}{\ln(\alpha)}$$
- **Behavioral Fit**:
  - Immediate-response performance channels (search, direct-response social, retargeting).

### B. Delayed Adstock (`type: "delayed"`)

Captures a buildup phase where maximum impact occurs $\theta$ periods after initial exposure.

$$\text{Weights}_l = \alpha^{(l - \theta)^2}, \quad l \in [0, l_{\max}]$$

- **Parameters**:
  - `alpha` ($\alpha \in (0, 1)$): Decay rate post-peak.
  - `theta` ($\theta \ge 0$): Delay period until peak effectiveness.
- **Behavioral Fit**:
  - High-consideration purchases (automotive, luxury, B2B) and brand-building media (TV, sponsorships).

### C. Weibull Adstock (`type: "weibull_cdf"` / `"weibull_pdf"`)

Two-parameter distribution capable of modeling skewed, delayed, or heavy-tailed memory curves.

- **Parameters**:
  - `shape` ($k > 0$): $k < 1$ produces heavy-tailed immediate decay; $k > 1$ produces S-shaped delayed peak.
  - `scale` ($\lambda > 0$): Controls duration/stretch of the lag window.
- **Behavioral Fit**:
  - Channels where rigid geometric decay is too restrictive and flexible shapes are needed.

---

## 2. Saturation Functions (Diminishing Returns)

Saturation models the non-linear relationship where successive spend yields diminishing incremental returns.

### A. Logistic Saturation (`type: "logistic"`)

Standard sigmoidal response curve.

$$f(x) = \frac{1 - e^{-\lambda x}}{1 + e^{-\lambda x}} = \tanh\left(\frac{\lambda x}{2}\right)$$

- **Parameters**:
  - `lam` ($\lambda > 0$): Transition/steepness rate.
- **Properties**: Strictly concave for $x > 0$ with normalized asymptote at 1.0.

### B. Hill Saturation (`type: "hill"` / `"hill_sigmoid"`)

Biochemical saturation curve with distinct threshold and saturation parameters.

$$f(x) = \frac{x^S}{K^S + x^S}$$

- **Parameters**:
  - `K` ($K > 0$): Half-saturation spend level ($f(K) = 0.5$).
  - `S` ($S > 0$): Hill slope parameter. $S > 1$ produces an S-curve with initial threshold before rapid growth; $S \le 1$ produces concave diminishing returns.
- **Behavioral Fit**:
  - Channels with minimum effective frequency (threshold effect before noticeable return).

### C. Hyperbolic Tangent (`type: "tanh"` / `"tanh_baselined"`)

$$f(x) = \tanh(b \cdot x)$$

- Smooth diminishing returns with sharp initial gradient. Ideal for channels operating at moderate spend volumes.

### D. Michaelis-Menten (`type: "michaelis_menten"`)

$$f(x) = \frac{\alpha \cdot x}{k + x}$$

- Non-inflected concave curve. Appropriate for performance search where every dollar immediately faces auction diminishing returns without threshold dynamics.

---

## 3. Prior Specification Best Practices

- Avoid inventing hard-coded "typical" channel parameters (e.g. asserting carryover is universally 0.4 for social).
- Rely on weakly informative priors centered on plausible domain scales, allowing the MCMC sampler to update posteriors based on empirical likelihood evidence.
- Run `evaluate_prior_sensitivity` when assessing how prior choices influence commercial conclusions.
