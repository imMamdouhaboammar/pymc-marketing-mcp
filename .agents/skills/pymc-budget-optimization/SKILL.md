---
name: pymc-budget-optimization
version: 3.0.0
description: Use when a user asks to simulate a spend change, reallocate or cut a fixed budget, optimize media allocation, or plan weekly flighting for a season or campaign.
---
# PyMC Budget Optimization

Turns an approved MMM into spend decisions: what happens under a specific change, how a fixed budget should be split, and how spend should be timed week by week. PyMC-Marketing computes every response and allocation on the server. The agent translates the user's plan into inputs faithfully and explains the result with its uncertainty.

## Entry checks (all required)

1. `get_model_status(model_id)` confirms the model, its channels, and its `dims`.
2. The model's diagnosis is `approved` or `approved_with_caution`. If unknown, run `pymc-diagnostics-gate`. A rejected model gets no budget answer of any kind, approximate ones included.
3. You know the user's constraints: total budget and horizon, channel floors and caps, fixed commitments (TV contracts, sponsorships), and whether the goal is revenue, conversions, or profit.

## Choose the operation

| The user says | Operation | Answers |
| --- | --- | --- |
| "What if we move 30% from TV to Meta?" / "What if we cut Google by 50k?" | `simulate_budget` | The outcome of one specific plan |
| "How should we split 400k across channels?" / "Cut 20% with the least damage" | `optimize_budget` | The best static split under constraints |
| "Plan the 12 weeks before Ramadan" / "Front-load Q4" | `optimize_flighting` | A week-by-week schedule with carryover |

For panel (geo) models or long horizons on a remote connection, use `submit_budget_optimization_job` or `submit_flighting_optimization_job` with the same config plus an `idempotency_key`, and hand off to `pymc-job-resilience`.

## Budget units

The server builds its comparison baseline from each channel's spend over the most recent `planning_periods` of history, rescaled to the requested budget. Say the budget and horizon back to the user in one sentence before calling ("400k across the next 8 weeks"). After the call, compare `baseline_allocation` with the user's actual recent spend; if they do not match in scale, stop and clarify units before presenting any recommendation.

## Call templates

`simulate_budget` (one scenario; channel names must match the model exactly):

```json
{"config": {
  "model_id": "<approved model_id>",
  "planning_periods": 8,
  "changes": {
    "tv_spend":   {"type": "add_spend", "value": -36000},
    "meta_spend": {"type": "add_spend", "value": 36000}
  }
}}
```

A transfer must keep the total unchanged. Percent changes on two channels with different spend levels do not balance: -30% of a large TV budget and +30% of a smaller Meta budget is a net cut. For "move 30% of TV to Meta", take TV's baseline spend over the horizon from a confirmed source (the user, or `baseline_allocation` from an earlier simulation), compute the amount moved, and pass that same amount as `add_spend` with opposite signs. The example assumes 120k of TV spend over 8 periods. If the baseline cannot be confirmed, ask the user for the absolute amount to move.

Change types: `percent_change` (value 30 means +30%), `relative` (value 0.3 means +30%), `multiply_spend` (1.3 means x1.3), `add_spend` / `absolute` (add the value in spend units), `set_spend` (replace spend with the value). Negative resulting spend is rejected. For panel models use `cell_changes`: `[{"channel": "meta_spend", "dimensions": {"geo": "KSA"}, "type": "percent_change", "value": 20}]`.

`optimize_budget` (static split):

```json
{"config": {
  "model_id": "<approved model_id>",
  "budget": 400000,
  "planning_periods": 8,
  "constraints": {
    "tv_spend":     {"fixed": 120000},
    "search_spend": {"min": 60000},
    "tiktok_spend": {"max": 50000}
  }
}}
```

Each constraint takes `min`, `max`, or `fixed`, all non-negative. Panel models reject channel-level constraints with `DIMENSIONAL_CONSTRAINT_REQUIRED`; use `cell_constraints` with an exact `dimensions` selector instead.

`optimize_flighting` (weekly schedule):

```json
{"config": {
  "model_id": "<approved model_id>",
  "total_budget": 600000,
  "planning_weeks": 12,
  "objective": "maximize_net_profit",
  "financial": {"kpi_unit": "revenue", "revenue_per_outcome": 1.0, "gross_margin_rate": 0.4},
  "channel_constraints": [
    {"channel": "tv_spend",   "min_weekly": 5000, "max_weekly": 40000, "pattern": "frontloaded"},
    {"channel": "meta_spend", "max_weekly": 30000, "pattern": "flat"}
  ]
}}
```

- `objective`: `maximize_response` (default) or `maximize_net_profit` (needs `financial`). For a return floor ("keep iROAS above 3"), set `target_iroas_min` with either objective. The schema also accepts `target_roas`, but the current server evaluates it as expected response (see the returned `objective_definition`), so do not promise the user a ROAS-targeting objective.
- `pattern` per channel: `flat`, `frontloaded`, `backloaded`, `pulsed`. Use `frontloaded` for awareness ahead of a peak (pre-Ramadan, pre-White Friday); `backloaded` to concentrate spend near a sale date; `pulsed` for burst-and-rest plans.
- `financial` replaces the legacy `margin_pct`. For leads or conversions, set `kpi_unit` and `revenue_per_outcome` from the user's own value per conversion; never invent it.

## Reading the results

- `simulate_budget`: `scenario_allocation`, `baseline_allocation`, and the posterior outcome comparison. Report the expected change with its interval, then `warnings` and `caveats`.
- `optimize_budget`: `recommended_allocation`, `baseline_allocation`, per-channel `spend_change_pct`, `binding_constraints` (which floors and caps shaped the answer), `economic_verdict` and `economic_warnings`, `channel_confidence`, and `identifiability_risks`.
- `optimize_flighting`: `weekly_schedule`, `allocated_budget`, `budget_residual`, `solver_status`, posterior response, `net_profit` when financial inputs were given, and `warnings`.

Warnings that must reach the user:

- `EXTRAPOLATION_RISK`: recommended spend goes above 1.5x the channel's historical 95th percentile (current server policy). The response there is poorly supported; suggest a staged increase or a test.
- `IDENTIFIABILITY_RISK` and `channel_confidence` of `low_sparse_history`: the data barely pins this channel down. Do not present a large move into it as reliable.
- `approved_with_caution` from the gate: the caution stays attached to the recommendation.

## When the optimizer fails

`OPTIMIZATION_INFEASIBLE` or `OPTIMIZATION_FAILED` means the floors, caps, fixed amounts, and budget cannot all hold, or the solver did not converge. Show the user the numbers that collide (for example: fixed TV 120k plus search floor 300k exceeds the 400k budget) and ask which to change. Never relax a constraint on your own and never substitute a hand-built split.

## Marketing interpretation

- Lead with the move: "shift about 18% from TV into Search and Meta over the next 8 weeks". Then the expected result range, then the risks.
- Explain *why* in one line using marginal returns: money moves from channels on the flat part of their curves to channels that still respond.
- Recommend staged moves inside historical spend support, with a check-in after a few weeks, especially when extrapolation or identifiability warnings appear.
- For Ramadan, Eid, or White Friday plans, confirm the model has a control for that event. Without one, say the plan rests on average seasonality.
- A recommendation is a model-based plan. Pair large moves with a measurement plan (`recommend_next_measurement`, `pymc-lift-calibration`).

## Stop conditions

Stop when the model is rejected or undiagnosed, when the dataset changed after fitting (`DATASET_FINGERPRINT_MISMATCH`: refit first), when units cannot be confirmed, or when constraints conflict and the user has not chosen which to relax.
