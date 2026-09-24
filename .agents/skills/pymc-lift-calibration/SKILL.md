---
name: pymc-lift-calibration
version: 3.0.0
description: Use when a user has lift-test, geo-experiment, holdout, or conversion-lift results to calibrate an existing MMM, or wants to inspect calibrated-model lineage.
---
# PyMC Lift Calibration

Feeds experiment results into the MMM so channel effects agree with what was measured directly. The server fits a new calibrated child model and leaves the parent untouched. The child must pass its own diagnosis before it drives any decision.

## Entry checks

1. A completed parent MMM: `get_model_status(model_id)`. Its channel names are the only valid `channel` values.
2. Experiment results with, for each test, the channel, the spend level before the test, the spend change, the measured incremental outcome, and its standard error. Ask for anything missing.
3. The experiment measured the same outcome as the model target (revenue with revenue, orders with orders) over a known period.

## Translate the experiment into the server contract

Each lift test becomes one `LiftTestMeasurement`:

| Field | Meaning | Where it comes from |
| --- | --- | --- |
| `channel` | Model channel column, exact name | Parent model config |
| `geo` | Panel value when the model has `dims` (for example `"KSA"`) | Test market |
| `x` | Spend level of the channel before the test, in the model's spend units and time grain | Media plan or platform spend during the test window |
| `delta_x` | Spend change applied during the test (> 0) | Test design: extra spend in treatment, or spend removed in a holdout expressed as a positive change |
| `delta_y` | Incremental outcome measured | Experiment readout, same units as the model target |
| `sigma` | Standard error of `delta_y` (> 0) | Experiment readout |
| `description` | Study name and dates | For lineage |

On `sigma`: use the standard error the study reports. If it only reports a symmetric 95% interval from a normal-approximation analysis, `sigma` is about the interval width divided by 3.92; confirm that assumption with the user before using it. Never shrink `sigma` to make the experiment count for more.

## Call

```json
{"input": {
  "model_id": "<parent model_id>",
  "lift_tests": [
    {"channel": "meta_spend", "geo": null, "x": 25000, "delta_x": 10000, "delta_y": 31000, "sigma": 7500,
     "description": "Meta conversion lift, 2026-03-01 to 2026-03-28"}
  ],
  "sampler": {"draws": 1000, "tune": 1000, "chains": 4, "target_accept": 0.9}
}}
```

`calibrate_mmm` refits the model, so expect minutes of sampling. Registered experiments can be passed as `experiment_ids` instead of inline `lift_tests`.

## After calibration

1. Record the child `model_id` in the ID ledger next to its parent. `provenance.parent_model_id` confirms the link; `marketing://models/{model_id}/lineage` shows the direct parent record.
2. Run `diagnose_mmm` on the **child**. Approval never carries over from the parent.
3. Only an `approved` or `approved_with_caution` child may feed `get_incremental_roas` or budget tools.
4. Compare parent and child evidence (`get_channel_contributions`, `get_incremental_roas` on each approved model) to show the user what the experiment changed.

## Marketing interpretation

- A well-run randomized lift test is the strongest evidence for the tested channel, market, and period. Calibration carries that evidence into the model; it does not make every other channel's estimate experimental.
- If the experiment and the parent model disagreed strongly, say so and say which way the calibrated model moved. Hiding the disagreement removes the most useful information the user has.
- Conversion-lift studies run inside an ad platform measure that platform's own incrementality with its own methodology. Treat them as experiments, and keep their measurement window in `description`.
- Keep experiment uncertainty and model uncertainty separate in the write-up.
- Suggest the next test where the calibrated model is still most uncertain (`recommend_next_measurement` on the child).

## Stop conditions

Stop when the parent model does not exist or cannot load, when a test lacks `x`, `delta_x`, `delta_y`, or `sigma` and the user cannot supply them, when the experiment's outcome does not match the model target, or when the child fails its diagnosis for a requested decision.
