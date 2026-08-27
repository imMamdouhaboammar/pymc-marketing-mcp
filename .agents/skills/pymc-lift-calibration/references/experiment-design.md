# Geo-Experiment & Lift Test Design Guide

This guide details best practices for designing, sizing, and interpreting randomized marketing incrementality tests for Bayesian MMM calibration.

---

## 1. Geo-Lift / Matched Market Test Design

Randomizing marketing spend at the geographic Designated Market Area (DMA) level prevents user-level tracking loss while isolating causal lift.

### Design Protocol:
1. **Market Matching**: Use dynamic time warping (DTW) or synthetic controls to match Treatment DMAs with highly correlated Control DMAs.
2. **Pre-Test Calibration Window**: Establish a 4–8 week pre-test baseline to verify pre-treatment parallel trends.
3. **Treatment Intervention**: Scale spend by $\Delta x$ in Treatment DMAs while holding Control DMAs at baseline spend $x$.
4. **Post-Test Cooldown**: Monitor response for 2–4 weeks post-flight to capture carryover adstock effects.

---

## 2. Converting Test Results for PyMC-Marketing

PyMC-Marketing requires:
- `x`: Baseline spend in test markets.
- `delta_x`: Incremental spend applied during test.
- `delta_y`: Incremental KPI response observed in treatment vs synthetic control.
- `sigma`: Standard error of $\Delta y$.

$$\sigma = \frac{\text{Upper CI}_{95\%} - \text{Lower CI}_{95\%}}{2 \times 1.96}$$
