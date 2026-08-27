# MCMC Diagnostics & Troubleshooting Guide

This guide details the statistical theory, numerical mechanics, and systematic remediation protocols for No-U-Turn Sampler (NUTS) diagnostics in PyMC-Marketing.

---

## 1. Divergences: Detection & Anatomy

### What is a Divergence?
In Hamiltonian Monte Carlo (HMC) and NUTS, a virtual particle simulates Hamiltonian dynamics across the negative log-posterior energy landscape using numerical leapfrog integration:
$$\theta(t + \epsilon) = \theta(t) + \epsilon \cdot M^{-1} p(t + \epsilon/2)$$
A **divergent transition** occurs when the simulated trajectory encounters a region of extreme posterior curvature where the Taylor series approximation of the gradient breaks down, causing the simulated energy $H(\theta, p)$ to diverge from the initial Hamiltonian $H(\theta_0, p_0)$:
$$|H(\theta^*, p^*) - H(\theta_0, p_0)| > \Delta_{\text{threshold}}$$

### Root Causes in Marketing Mix Models:
1. **Neal's Funnel in Hierarchical Parameters**: Group-level standard deviations $\sigma_g \to 0$ create a steep narrow funnel that leapfrog steps overshoot.
2. **Hill Saturation Slope Parameters**: When Hill slope $S > 3$ with wide prior bounds, the gradient near the threshold inflection point is nearly infinite.
3. **Collinear Spend Regressors**: Correlated channels produce an elongated, diagonal ridge in posterior space.

### Remediation Steps:
1. **Increase `target_accept`**: Elevate from 0.90 to 0.95 (or 0.98). This forces NUTS to adapt a smaller step size $\epsilon$:
   $$\epsilon_{\text{new}} < \epsilon_{\text{old}}$$
2. **Increase Warmup `tune`**: Extend warmup iterations to 2000 to improve dense mass-matrix adaptation.
3. **Reparameterize / Constrain Priors**: Replace unconstrained Hill saturation with Logistic saturation, or place informative Gamma/HalfNormal priors on saturation parameters.

---

## 2. Gelman-Rubin Diagnostic ($\hat{R}$)

$\hat{R}$ (potential scale reduction factor) compares the variance between independent MCMC chains to the variance within each chain:
$$\hat{R} = \sqrt{\frac{W + \frac{1}{N}(B - W)}{W}}$$
where $B/N$ is between-chain variance and $W$ is mean within-chain variance.

- **$\hat{R} \le 1.01$**: Clean convergence. Chains have mixed thoroughly and reached the same stationary posterior distribution.
- **$1.01 < \hat{R} \le 1.05$**: Mild non-convergence (Caution zone).
- **$\hat{R} > 1.05$**: Hard failure (Rejected). Chains are exploring distinct local modes or have not finished warmup.

---

## 3. Effective Sample Size (ESS)

MCMC samples are serially autocorrelated. ESS estimates the number of independent samples with equivalent statistical precision:
$$\text{ESS} = \frac{N}{1 + 2 \sum_{k=1}^{\infty} \rho_k}$$

- **Bulk ESS**: Measures precision of central tendency (mean, median). Bulk ESS $\ge 400$ guarantees standard error of the mean $< 2.5\%$ of posterior standard deviation.
- **Tail ESS**: Measures precision in the distribution tails (2.5% and 97.5% quantiles). Essential for reliable 94% HDI credible intervals.

---

## 4. Posterior Predictive Coverage

Checks whether observed actuals $y_{\text{obs}}$ fall inside the model's posterior predictive distribution interval:
$$\text{Coverage} = \frac{1}{T} \sum_{t=1}^T \mathbb{I}\left( y_t \in [\text{HDI}_{94\%, \text{lower}}, \text{HDI}_{94\%, \text{upper}}] \right)$$
- $\text{Coverage} \ge 80\%$: Well-calibrated likelihood error model.
- $\text{Coverage} < 50\%$: Severe under-dispersion or model misspecification.
