# MCMC Troubleshooting & Convergence Guide

This reference provides exact diagnosis and remediation procedures for MCMC sampling pathologies in PyMC-Marketing.

---

## 1. Hamiltonian Divergences

### Root Cause
A divergence occurs when the numerical leapfrog integrator encounters regions of extreme curvature in the continuous posterior geometry. The simulated trajectory departs from the true energy surface. Even a small number of divergences indicates that the Markov chain cannot reliably explore that portion of the parameter space, biasing posterior estimates.

### Geometry in MMMs
In Marketing Mix Models, divergences frequently occur in:
1. **Adstock Boundary Funnels**: When retention $\alpha \to 1.0$ or $\alpha \to 0.0$.
2. **Hill Saturation Valleys**: High interaction between half-saturation $K$ and slope $S$. When spend is low, $K$ is unidentifiable, creating a flat plateau with a steep canyon.

### Remediation Steps
1. **Increase `target_accept`**:
   - Default: `0.90`
   - Remediation: `0.95` or `0.98`
   - Mechanism: Reduces the leapfrog step size $\epsilon$, allowing the integrator to make smaller, more accurate steps.
2. **Increase Warmup / `tune`**:
   - Step from `tune=1000` to `tune=2000`. Gives dual averaging more steps to estimate the mass matrix metric.
3. **Re-parameterize Priors**:
   - Switch from unconstrained `hill` saturation to `logistic` saturation.
   - Constrain `l_max` to realistic business bounds (e.g. 4 to 8 weeks for digital channels instead of 26 weeks).

---

## 2. Gelman-Rubin $\hat{R}$ Diagnostic

### Root Cause
$\hat{R}$ (potential scale reduction factor) compares the variance between independent chains to the variance within each chain.
- $\hat{R} \approx 1.00$: Chains are well-mixed and exploring the same stationary distribution.
- $\hat{R} > 1.01$: Minor non-stationarity or slow mixing.
- $\hat{R} > 1.05$: Definite convergence failure. Chains are stuck in distinct local modes or have not traversed the distribution.

### Remediation Steps
1. **Collinear Channels**:
   - If two channels are colinear ($r \ge 0.90$), chain 1 may attribute 80% to Channel A and 20% to Channel B, while chain 2 attributes 20% to Channel A and 80% to Channel B.
   - Fix: Combine channels into a unified channel group or add an informative prior / experimental lift calibration on one of them.
2. **Over-parameterized Controls**:
   - Having too many control variables relative to sample size creates flat likelihood ridges.
   - Fix: Remove non-significant controls or apply regularizing priors.
3. **Chain Count**:
   - Always run at least 4 chains (`chains=4`) with independent random initialization to ensure multimodal detection.

---

## 3. Effective Sample Size (ESS)

### Bulk ESS vs Tail ESS
- **Bulk ESS**: Evaluates the precision of mean and median estimates. Target $\ge 400$.
- **Tail ESS**: Evaluates the precision of extreme quantiles (e.g. 3rd and 97th percentiles used in 94% HDI intervals). Target $\ge 400$.

### Low ESS Recovery
- If ESS $< 50$, posterior draws have severe autocorrelation.
- Remediation: Double total draws (`draws=2000`) and investigate whether high adstock lags are causing slow autocorrelation decay in the Markov chain.
