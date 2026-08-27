# Lift Test Pre-Calibration Checklist

Run this checklist before passing experiment measurements into `calibrate_mmm`:

- [x] Experiment duration covered full media flight + carryover window (minimum 4 weeks).
- [x] Pre-test parallel trends validated between Treatment and Control geos ($R^2 > 0.85$).
- [x] Spend increment $\Delta x$ was strictly positive and isolated to test markets.
- [x] Measured incremental KPI $\Delta y$ accounts for baseline control growth.
- [x] Empirical standard error $\sigma$ is calculated from 95% confidence intervals:
  $$\sigma = \frac{\text{CI}_{\text{high}} - \text{CI}_{\text{low}}}{3.92}$$
- [x] Parent model `model_id` is verified and diagnosed.
