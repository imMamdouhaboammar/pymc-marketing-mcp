# MCMC Diagnostics & Troubleshooting Guide

This guide details the statistical theory, numerical mechanics, and systematic remediation protocols for No-U-Turn Sampler (NUTS) diagnostics in PyMC-Marketing.

---

## 1. Divergences: Detection & Anatomy

### What is a Divergence?
In Hamiltonian Monte Carlo (HMC) and NUTS, a virtual particle simulates Hamiltonian dynamics across the negative log-posterior energy landscape using numerical leapfrog integration:
$$\theta(t + \epsilon) = \theta(t) + \epsilon \cdot M^{-1} p(t + \epsilon/2)$$
A **divergent transition** occurs when the simulated trajectory encounters a region of extreme posterior curvature where the numerical approximation breaks down, causing the simulated energy to diverge:
$$|H(\theta^*, p^*) - H(\theta_0, p_0)| > \Delta_{\text{threshold}}$$

### Common Causes in Marketing Mix Models:
1. **Hierarchical Funneling**: Group-level standard deviations $\sigma_g \to 0$ create steep funnels that leapfrog steps overshoot.
2. **Hill Saturation Slopes**: High slope parameters $S > 3$ with wide prior bounds create near-vertical gradients.
3. **Collinear Channel Spend**: Highly correlated channels create narrow, diagonal ridges in posterior parameter space.

### Remediation Steps:
1. **Increase `target_accept`**: Elevate from 0.90 to 0.95 (or 0.98), forcing NUTS to adapt a smaller integration step size.
2. **Increase Warmup `tune`**: Extend warmup iterations to 2000 to improve mass-matrix adaptation.
3. **Regularize Priors**: Replace unconstrained parameters with weakly informative priors.

---

## 2. Gelman-Rubin Diagnostic ($\hat{R}$)

$\hat{R}$ compares the variance between independent MCMC chains to the variance within each chain:
- **$\hat{R} \le 1.01$**: Clean convergence. Chains have mixed thoroughly.
- **$1.01 < \hat{R} \le 1.05$**: Mild convergence friction (Caution zone).
- **$\hat{R} > 1.05$**: Hard failure (Rejected). Chains have not converged to the same posterior mode.

---

## 3. Effective Sample Size (ESS)

MCMC samples are autocorrelated. ESS measures the number of independent samples:
- **Bulk ESS**: Precision of mean/median estimates. Target: Bulk ESS $\ge 400$.
- **Tail ESS**: Precision of tail quantiles (2.5% and 97.5%). Critical for reliable 94% HDI bounds.

---

## 4. Decision Gate Authority

Production decision gate verdicts (`approved`, `caution`, `rejected`) are determined server-side by `diagnose_mmm`. Client-side tools must respect the server's verdict.
