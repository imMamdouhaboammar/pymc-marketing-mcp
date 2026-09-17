# Incrementality Triangulation Framework

Triangulation unites observational MMM, digital touchpoint metrics, and randomized experiments into a coherent decision framework.

---

## 1. The Attribution Hierarchy

| Methodology | Primary Strength | Structural Limitation | Role in Marketing Science |
|---|---|---|---|
| **Digital Touchpoint Tracking** | Granular user-level clicks/views | Selection bias, ignores offline/privacy | Tactical creative rotation |
| **Observational MMM** | Holistic, macro view across all spend | Confounding, endogeneity bias | Macro budget allocation across channels |
| **Randomized Experiments (Lift)** | Localized causal proof | Costly, localized point-in-time | Likelihood anchors in Bayesian calibration |

---

## 2. Scientific Principles of Incrementality

1. **Observational MMM is Associational**: Without experimental anchors, an MMM estimates conditional statistical relationships.
2. **Correlation $\ne$ Incrementality**: High-intent channels (e.g. brand search) often exhibit high total correlation with revenue because spend scales with existing demand.
3. **Triangulating with Experiments**: When a randomized geo-lift experiment is conducted, its measurement $(\Delta x, \Delta y, \sigma)$ can be passed to `calibrate_mmm` to anchor the model's saturation curve to experimentally verified incrementality.
