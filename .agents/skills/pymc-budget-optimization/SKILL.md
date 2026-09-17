---
name: pymc-budget-optimization
version: 2.1.0
description: Use when a user asks to simulate spend, reallocate a fixed budget, optimize media allocation, or plan weekly flighting.
---

# PyMC Budget Optimization

Never recreate PyMC-Marketing optimization or scenario arithmetic in the LLM. The server is authoritative.

## Choose the right operation

- `simulate_budget`: evaluate a user-specified counterfactual allocation/change. It answers “what if?”.
- `optimize_budget`: static allocation of a fixed budget subject to supplied bounds/constraints.
- `optimize_flighting`: dynamic weekly allocation/pattern problem across a planning horizon.

## Gate and workflow

1. Identify the exact model and check `get_model_status` when state is unclear.
2. Require persisted `diagnose_mmm` results. If the model is rejected, stop; do not manually estimate an allocation.
3. Translate user constraints faithfully. Never silently relax infeasible floors/caps or invent missing business constraints.
4. Call the matching server decision tool.
5. Preserve posterior uncertainty, diagnostic context, optimizer/solver status, identifiability warnings, and extrapolation warnings.

The current server flags `EXTRAPOLATION_RISK` when recommended weekly spend materially exceeds its implemented historical-support threshold (1.5× the channel’s historical 95th percentile). Treat that as current server policy, not a universal scientific rule. Do not suppress the warning or present far-out response curves as well-supported evidence.

An `approved_with_caution` model can pass the server gate, but the caution remains part of the decision. If uncertainty or identifiability is material, suggest measurement/calibration rather than converting a posterior distribution into false certainty.
