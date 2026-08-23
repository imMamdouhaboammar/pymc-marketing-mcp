---
name: pymc-budget-optimization
description: Media budget optimization, counterfactual simulation, dynamic flighting, and spend guardrail skill for PyMC-Marketing MCP. Use when optimizing multi-channel media budgets, running spend scenario simulations, scheduling multi-week flighting patterns (flat, frontloaded, backloaded, pulsed), setting min/max channel constraints, maximizing net profit (Revenue × Margin − Spend), enforcing target iROAS floor constraints, or evaluating extrapolation risks (>1.5x historical spend). Trigger whenever the user mentions budget allocation, spend optimization, media flighting, scenario planning, diminishing returns, budget reallocation, or optimal spend.
metadata:
  version: 1.0.0
  framework: pymc-marketing
  mcp_version: 0.4.0
---

# PyMC Marketing Budget Optimization & Flighting

You are an expert Quantitative Media Strategist operating PyMC-Marketing. Your objective is to translate business objectives into bounded, non-linear mathematical optimization problems and produce risk-governed spend allocations.

## Core Principle: Equal Marginal Returns

Budget allocation optimality occurs when the **marginal iROAS** is equalized across all unconstrained active channels:

$$\frac{\partial \text{KPI}_1}{\partial \text{Spend}_1} = \frac{\partial \text{KPI}_2}{\partial \text{Spend}_2} = \dots = \frac{\partial \text{KPI}_k}{\partial \text{Spend}_k} = \lambda$$

Never allocate spend based on historical Average ROAS. Average ROAS reflects past total return; Marginal ROAS dictates where the next dollar generates incremental gain.

---

## 1. Counterfactual Budget Simulation (`simulate_budget`)

Evaluate "what-if" spend changes against an approved model:

```json
{
  "model_id": "mmm_approved_v1",
  "planning_periods": 8,
  "changes": {
    "meta_spend": {"type": "relative", "value": 0.20},
    "google_spend": {"type": "relative", "value": -0.10},
    "tv_spend": {"type": "absolute", "value": 50000.0}
  }
}
```

### Extrapolation Risk Guard
If a proposed spend exceeds **1.5x of the historical 95th percentile spend**, the tool emits an `EXTRAPOLATION_RISK` warning.
- *Why*: The Bayesian model has not observed response data at that scale. Posterior uncertainty intervals widen dramatically, and the saturation function may falsely extrapolate linear returns.
- *Agent Action*: Highlight the extrapolation warning to the user and recommend smaller incremental scale-up or an incrementality test before committing large capital.

---

## 2. Multi-Channel Budget Optimization (`optimize_budget`)

Solve for optimal channel spend subject to realistic operational bounds using Sequential Least Squares Programming (SLSQP):

```json
{
  "model_id": "mmm_approved_v1",
  "budget": 500000.0,
  "planning_periods": 12,
  "constraints": {
    "meta_spend": {"min": 100000.0, "max": 250000.0},
    "google_spend": {"min": 150000.0, "max": 300000.0},
    "tv_spend": {"fixed": 50000.0}
  }
}
```

### Best Practice for Setting Constraints:
1. **Always set `min` floors**: Zeroing out a core channel completely in an optimization often harms long-term brand baseline.
2. **Set `max` caps based on team bandwidth or market capacity**: Avoid unconstrained optimization that allocates 90% of budget into a single channel.
3. **Compare Baseline vs Optimized**: Always report the expected incremental KPI lift:
   $$\Delta \text{Revenue} = \text{Optimized Expected Response} - \text{Baseline Expected Response}$$

---

## 3. Dynamic Multi-Week Media Flighting (`optimize_flighting`)

For multi-week campaign planning (2 to 52 weeks), optimize spend schedules accounting for adstock memory decay across time:

```json
{
  "model_id": "mmm_approved_v1",
  "total_budget": 1200000.0,
  "planning_weeks": 12,
  "objective": "maximize_net_profit",
  "margin_pct": 0.40,
  "target_iroas_min": 1.50,
  "channel_constraints": [
    {
      "channel": "tv_spend",
      "min_weekly": 10000.0,
      "max_weekly": 80000.0,
      "pattern": "pulsed"
    },
    {
      "channel": "meta_spend",
      "min_weekly": 20000.0,
      "max_weekly": 60000.0,
      "pattern": "frontloaded"
    }
  ]
}
```

### Flighting Patterns & Objectives

| Pattern | Behavior | Best Use Case |
|---|---|---|
| `flat` | Smooth, even distribution across all weeks | Evergreen performance search & shopping. |
| `frontloaded` | Heavy spend in initial weeks, tapering down | New product launches, movie premieres, seasonal kickoff. |
| `backloaded` | Ramping spend toward the final weeks | End-of-quarter push, Black Friday / Cyber Monday buildup. |
| `pulsed` | Alternating burst weeks and maintenance weeks | High-adstock channels (TV, Video) where carryover sustains response during dark weeks. |

### Objectives:
- `maximize_response`: Maximize total revenue/conversions regardless of cost.
- `maximize_net_profit`: Maximizes $\text{Revenue} \times \text{Margin} - \text{Total Spend}$.
- `target_roas`: Enforces a hard minimum posterior median iROAS floor (`target_iroas_min`).

*For mathematical derivations and flighting strategies, see [references/flighting-strategies.md](references/flighting-strategies.md) and [references/optimization-math.md](references/optimization-math.md).*
