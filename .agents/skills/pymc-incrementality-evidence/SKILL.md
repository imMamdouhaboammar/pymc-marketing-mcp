---
name: pymc-incrementality-evidence
version: 1.0.0
description: Use when a user asks about channel contribution, total or marginal iROAS, response curves, incrementality evidence, or what an MMM supports.
---

# PyMC Incrementality Evidence

All model-dependent numbers come from MCP outputs. Never compute channel contribution, iROAS, posterior intervals, or response curves from prose or raw coefficients.

## Keep quantities distinct

- **Contribution**: posterior allocation of modeled outcome to a channel; not automatically experimental causality.
- **Total iROAS**: incremental return over the evaluated spend quantity as returned by the server.
- **Marginal iROAS**: return at the margin; it can differ materially from total iROAS under saturation.
- **Response curve / saturation**: modeled response across spend support; do not silently extrapolate it into unobserved ranges.
- **Predictive evidence**: ability to predict held-out outcomes; not causal identification.
- **Causal evidence**: requires assumptions/design beyond sampler health; lift experiments can strengthen identification but do not make every MMM quantity universally causal.

`get_channel_contributions` and `get_response_curves` are descriptive and may return gate context even for rejected models; label such evidence non-decision-grade. `get_incremental_roas` is decision-gated in the current implementation and must follow diagnosis. Preserve all returned intervals, warnings, provenance, and `decision_gate` context.

Use `recommend_next_measurement` only for the limited server-generated measurement suggestions it actually returns; do not claim it globally optimizes experimental information gain. When uncertainty changes the decision, route to `pymc-lift-calibration` or a new measurement rather than inventing certainty.
