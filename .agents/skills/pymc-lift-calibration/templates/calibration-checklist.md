# Lift Test Pre-Calibration Checklist

Run this checklist before passing experiment measurements into `calibrate_mmm`:

- [ ] Experiment duration covered full media flight plus carryover window.
- [ ] Pre-test parallel trends verified between Treatment and Control geos.
- [ ] Incremental spend $\Delta x$ was strictly positive and isolated to test markets.
- [ ] Measured incremental KPI $\Delta y$ accounts for baseline control movement.
- [ ] Standard error $\sigma$ is positive ($\sigma > 0$) and appropriately calculated.
- [ ] Parent model `model_id` is verified and diagnosed.
