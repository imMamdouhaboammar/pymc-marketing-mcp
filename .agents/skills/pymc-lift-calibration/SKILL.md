---
name: pymc-lift-calibration
version: 2.1.0
description: Use when a user has lift-test or experiment measurements to calibrate an existing MMM or inspect calibrated-model lineage.
---

# PyMC Lift Calibration

Calibration adds experiment-derived measurement information to a new model fit. Keep the original model and its lineage intact.

## Workflow

1. Identify the completed parent MMM and the lift measurements. Use the exact `calibrate_mmm` input contract (`channel`, optional `geo`, baseline `x`, `delta_x`, measured `delta_y`, and `sigma`). Do not reverse-engineer `sigma` from a published interval unless the study’s statistical assumptions justify that conversion and the user has supplied enough information.
2. Call `calibrate_mmm`. The server creates a calibrated child model rather than overwriting the parent.
3. Record the child model ID and inspect `marketing://models/{model_id}/lineage` when provenance matters.
4. Run `diagnose_mmm` on the **child**. Diagnostic approval does not inherit from the parent.
5. Only after the child’s own gate passes may it be used for gated iROAS/budget decisions.

A well-designed randomized lift experiment can supply stronger local causal evidence for the measured intervention than an observational MMM alone. Calibration does not transform every model component into indisputable causal truth, and disagreement between the experiment and MMM should be reported rather than hidden.

Preserve experiment uncertainty and model uncertainty separately where the tools expose them. Stop when the experiment lacks the measurement fields the server requires rather than inventing them.
