# Geo-Experiment & Lift Test Design Guide

This guide details best practices for designing and interpreting randomized marketing incrementality tests for Bayesian MMM calibration.

---

## 1. Geo-Lift / Matched Market Test Design

Randomizing marketing spend at the geographic market level isolates causal lift.

### Design Protocol:
1. **Market Matching**: Match Treatment DMAs with correlated Control DMAs using synthetic controls or dynamic time warping.
2. **Pre-Test Baseline Window**: Establish 4–8 weeks pre-test baseline to verify parallel trends.
3. **Treatment Intervention**: Apply spend delta $\Delta x$ in Treatment DMAs while holding Control DMAs at baseline spend $x$.
4. **Post-Test Cooldown**: Observe carryover decay post-flight.

---

## 2. Converting Test Results for `calibrate_mmm`

The `calibrate_mmm` tool accepts:
- `channel`: Target marketing channel.
- `x`: Baseline spend in test markets.
- `delta_x`: Incremental spend applied during the test ($\Delta x > 0$).
- `delta_y`: Measured incremental KPI response.
- `sigma`: Standard error of $\Delta y$ ($\sigma > 0$).

When converting confidence intervals to standard error $\sigma$:
$$\sigma = \frac{\text{Upper CI}_{95\%} - \text{Lower CI}_{95\%}}{2 \times 1.96}$$
*Caveat*: This formula assumes a symmetric Gaussian sampling distribution. Do not apply it blindly to skewed or Bayesian credible intervals without verifying normality.
