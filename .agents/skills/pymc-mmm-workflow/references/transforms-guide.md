# Adstock and Saturation Transforms Guide

This guide details the mathematical foundations, parameter interpretations, and practical selection rules for media transformation functions available in PyMC-Marketing.

---

## 1. Adstock Transformations (Carryover / Memory)

Adstock models the delayed and decaying effect of advertising impressions or spend over time.

### A. Geometric Adstock (`type: "geometric"`)

The classical Koyck transformation. Each period's effective adstock is a weighted decay of prior spend.

$$\text{Adstock}_t = x_t + \alpha \cdot \text{Adstock}_{t-1}$$

- **Parameters**:
  - `alpha` ($\alpha \in [0, 1)$): Retention rate. $\alpha = 0$ means immediate decay; $\alpha = 0.8$ means 80% carryover into the next period.
  - `l_max` (default: 8): Maximum lag window computed.
- **Half-Life Formula**:
  $$t_{1/2} = \frac{-\ln(2)}{\ln(\alpha)}$$
- **When to Choose**:
  - Performance marketing (Search, Meta direct-response, display retargeting).
  - Fast-moving consumer goods with rapid conversion cycles.

### B. Delayed Adstock (`type: "delayed"`)

Captures a buildup phase where maximum impact occurs $k$ periods after initial exposure.

$$\text{Weights}_l = \alpha^{(l - \theta)^2}, \quad l \in [0, l_{\max}]$$

- **Parameters**:
  - `alpha` ($\alpha \in (0, 1)$): Decay rate post-peak.
  - `theta` ($\theta \ge 0$): Delay period until peak effectiveness.
- **When to Choose**:
  - TV brand campaigns, billboard/OOH, sponsorship events.
  - High-consideration purchases (automotive, B2B SaaS, luxury goods) with long consideration windows.

### C. Weibull Adstock (`type: "weibull_cdf"` / `"weibull_pdf"`)

Highly flexible two-parameter distribution capable of modeling skewed, delayed, or heavy-tailed memory curves.

- **Parameters**:
  - `shape` ($k > 0$): $k < 1$ produces heavy-tailed immediate decay; $k > 1$ produces S-shaped delayed peak.
  - `scale` ($\lambda > 0$): Controls duration/stretch of the window.
- **When to Choose**:
  - Multi-channel campaigns with uncertain lag dynamics.
  - Channels where geometric decay is too restrictive.

---

## 2. Saturation Functions (Diminishing Returns)

Saturation models the non-linear relationship where successive dollar increments yield progressively smaller incremental returns.

### A. Logistic Saturation (`type: "logistic"`)

Standard S-shaped sigmoidal response curve.

$$f(x) = \frac{1 - e^{-\lambda x}}{1 + e^{-\lambda x}} = \tanh\left(\frac{\lambda x}{2}\right)$$

- **Parameters**:
  - `lam` ($\lambda > 0$): Transition/steepness rate.
- **Properties**: Strictly concave for $x > 0$ with normalized asymptote at 1.0.

### B. Hill Saturation (`type: "hill"` / `"hill_sigmoid"`)

Biochemical saturation curve with distinct threshold and saturation parameters.

$$f(x) = \frac{x^S}{K^S + x^S}$$

- **Parameters**:
  - `K` ($K > 0$): Half-saturation spend level ($f(K) = 0.5$).
  - `S` ($S > 0$): Hill slope/shape parameter. $S > 1$ produces an S-curve with initial threshold before rapid growth; $S \le 1$ produces strictly concave diminishing returns.
- **When to Choose**:
  - Channels with minimum effective frequency (where low spend does nothing, medium spend works well, high spend saturates).

### C. Hyperbolic Tangent (`type: "tanh"` / `"tanh_baselined"`)

$$f(x) = \tanh(b \cdot x)$$

- Smooth diminishing returns with sharp initial gradient. Ideal for channels operating at moderate spend volumes.

### D. Michaelis-Menten (`type: "michaelis_menten"`)

$$f(x) = \frac{\alpha \cdot x}{k + x}$$

- Non-inflected concave curve. Excellent for direct performance search where every dollar immediately faces diminishing bid auctions without threshold effects.

---

## 3. Transformation Selection Matrix

| Channel Archetype | Recommended Adstock | Recommended Saturation | Typical $l_{\max}$ (Weekly) |
|---|---|---|---|
| **Google Brand Search** | `none` or `geometric` ($\alpha \approx 0.1$) | `michaelis_menten` or `logistic` | 2–4 weeks |
| **Google Non-Brand Search** | `geometric` ($\alpha \approx 0.3$) | `logistic` | 4–6 weeks |
| **Meta Direct Response** | `geometric` ($\alpha \approx 0.4$) | `logistic` or `hill` | 4–8 weeks |
| **Linear / Connected TV** | `delayed` or `weibull_pdf` | `hill` ($S > 1$) | 8–16 weeks |
| **Digital Video / YouTube** | `geometric` ($\alpha \approx 0.5$) | `logistic` | 6–10 weeks |
| **Out of Home (OOH)** | `delayed` | `tanh` | 8–12 weeks |
| **Influencer / Creator** | `weibull_cdf` | `hill` | 6–12 weeks |
| **Direct Mail / Catalogs** | `delayed` ($\theta \approx 2$) | `logistic` | 8–14 weeks |
