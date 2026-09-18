# RFC 001: Long-Term Brand Effects & Bayesian VAR Integration

- **Status**: Draft / Prototype (Experimental)
- **Author**: Marketing Science Core Team
- **Date**: 2026-09-18
- **Target Seam**: `src/marketing_mcp/domain/long_term/`

---

## 1. Context & Motivation

Standard Media Mix Models (MMM) quantify short-term direct and carryover effects using adstock transformations (geometric, Weibull). However, brand-building investments (upper-funnel TV, sponsorship, display) frequently influence intermediate brand equity, brand search volume, and baseline sales over extended horizons ($H > 12$ weeks). Treating upper-funnel media purely through short-term ROAS undervalues long-term brand equity contribution.

## 2. Mathematical Formulation

We formulate the combined system as a Structural Vector Autoregression with Exogenous Variables (VARX(p)):

$$\mathbf{Y}_t = \mathbf{c} + \sum_{i=1}^p \mathbf{A}_i \mathbf{Y}_{t-i} + \mathbf{B} \mathbf{X}_t + \mathbf{\epsilon}_t, \quad \mathbf{\epsilon}_t \sim \mathcal{N}(\mathbf{0}, \mathbf{\Sigma})$$

Where:
- $\mathbf{Y}_t = [\text{BrandEquity}_t, \text{OrganicDemand}_t, \text{TargetRevenue}_t]^T$ (endogenous system)
- $\mathbf{X}_t = [\text{Spend}_{1, t}, \dots, \text{Spend}_{K, t}]^T$ (exogenous media investments)
- $\mathbf{A}_i$ governs dynamic feedback and persistence across endogenous brand assets.
- $\mathbf{B}$ measures immediate contemporaneous impact of media on brand equity and sales.
- $\mathbf{\Sigma}$ is the covariance matrix of innovations.

### Stability Condition
The companion matrix $\mathbf{F}$ must satisfy $\max |\text{eig}(\mathbf{F})| < 1$, ensuring all characteristic roots lie inside the complex unit circle. Non-stationary trajectories are flagged and rejected by diagnostic gates.

## 3. Prior Structure (Minnesota-Style Regularization)

To prevent parameter proliferation and over-fitting:
- Diagonal elements of $\mathbf{A}_1$ have Normal priors centered at $0.7$ (persistence of brand equity) with shrink parameter $\lambda_1$.
- Off-diagonal elements have Normal priors centered at $0$ with higher variance shrinkage $\lambda_2$.
- Exogenous media coefficients in $\mathbf{B}$ have HalfNormal priors enforcing non-negative marketing impact.

## 4. Impulse Response Functions (IRFs) & Long-Run Multipliers

The cumulative impulse response of outcome $j$ to an exogenous shock in media channel $k$ over horizon $H$:

$$\Psi_{j, k}(H) = \sum_{h=0}^H \frac{\partial Y_{j, t+h}}{\partial X_{k, t}}$$

The Long-Term Value Multiplier:

$$\text{Multiplier}_k = 1 + \frac{\sum_{h=1}^H \Psi_{\text{revenue}, k}(h)}{\Psi_{\text{revenue}, k}(0)}$$

This multiplier rolls up directly into MMM budget optimization and flighting decision provenance.
