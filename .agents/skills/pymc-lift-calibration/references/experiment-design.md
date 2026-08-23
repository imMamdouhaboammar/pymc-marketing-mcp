# Incrementality Experiment Design & Standard Error Derivation

This guide details methodologies for designing geo-experiments, matched market tests, and deriving inputs for Bayesian calibration.

---

## 1. Geo-Experiment Methodologies

### A. Matched Markets Testing
1. Pair test DMAs/geos with twin control DMAs based on historical time-series correlation in sales KPI.
2. Hold control geos at baseline spend $x$.
3. Increase test geos spend by $\Delta x$.
4. Compute Synthetic Difference-in-Differences (SDID) to estimate incremental lift $\Delta y$ and standard error $\sigma$.

### B. Cell-Based Conversion Lift (Platform Holdouts)
1. Split audience randomly into treatment (exposed to ads) and control (unexposed).
2. Measure conversion rate difference $\Delta \text{CVR} = \text{CVR}_{\text{treat}} - \text{CVR}_{\text{ctrl}}$.
3. Scale by total population to compute incremental volume $\Delta y$.

---

## 2. Deriving Calibration Inputs ($x, \Delta x, \Delta y, \sigma$)

### Confidence Interval Conversion Formulas

Given a reported $(1 - \alpha)$ Confidence Interval $[CI_{\text{lower}}, CI_{\text{upper}}]$:

1. Point Estimate:
   $$\Delta y = \frac{CI_{\text{upper}} + CI_{\text{lower}}}{2}$$

2. Standard Error ($\sigma$):
   $$\sigma = \frac{CI_{\text{upper}} - CI_{\text{lower}}}{2 \cdot z_{1 - \alpha/2}}$$

- For 95% Confidence ($z = 1.96$):
  $$\sigma = \frac{CI_{\text{upper}} - CI_{\text{lower}}}{3.92}$$
- For 90% Confidence ($z = 1.645$):
  $$\sigma = \frac{CI_{\text{upper}} - CI_{\text{lower}}}{3.29}$$

### Scaling Geo-Level Lift to National Scale
If the test was conducted in geos representing $p\%$ of national revenue (e.g. $p = 15\%$):
- National $\Delta x = \Delta x_{\text{geo}} / p$
- National $\Delta y = \Delta y_{\text{geo}} / p$
- National $\sigma = \sigma_{\text{geo}} / p$
