---
name: pymc-budget-optimization
description: >
  Optimize marketing budget allocations, run counterfactual spend simulations, and generate
  dynamic multi-period media flighting schedules with PyMC-Marketing. Use when the user asks
  how to allocate advertising spend across channels, simulate a budget reallocation, maximize
  net profit or revenue under spend constraints, build weekly media flighting schedules, or
  evaluate diminishing returns on future marketing plans — even if they do not explicitly say
  "optimization" (e.g., "how should I split $500k between Meta and Google", "simulate cutting TV
  budget by 20%", "find optimal channel mix", "build a flighting schedule for Q4"). Do NOT use
  for initial MMM model fitting (use pymc-mmm-workflow) or for fixing unconverged MCMC models
  (use pymc-diagnostics-gate).
version: 2.0.0
pack: marketing-science
inputs:
  - model_id
  - total_budget
  - channel_constraints
  - planning_periods
  - scenario_changes
requires:
  - decision_approved_model_id
produces:
  - optimal_spend_allocation
  - expected_incremental_kpi
  - marginal_iroas_distribution
  - multi_period_flighting_schedule
  - extrapolation_risk_report
gates:
  - diagnostic_gate_approved
  - constraints_feasible
  - non_negative_budget
fallback: pymc-diagnostics-gate
mutatesWorkspace: false
parallelSafe: true
neural_links:
  precursors:
    - pymc-mmm-workflow
    - pymc-diagnostics-gate
  continuations:
    - pymc-lift-calibration
  lateral_peers:
    - pymc-clv-customer-analytics
  recovery: pymc-diagnostics-gate
---

# PyMC Marketing Budget Optimization & Flighting

Translate business goals and budget constraints into bounded, uncertainty-aware mathematical optimization problems using PyMC-Marketing. Maximize incremental revenue or net profit across media channels and schedule dynamic weekly flighting patterns while respecting saturation ceilings and operational guardrails.

## Runtime Requirements (pre-flight)

Before executing budget allocation or scenario tools, verify:
- [ ] A fitted model exists with a valid `model_id`
- [ ] Model decision status is `approved` or `approved_with_caution` (check via `get_model_status`)
- [ ] Target budget is strictly positive ($> 0$)
- [ ] Lower and upper channel constraints are mathematically feasible:
  $$\sum \text{min\_spend}_c \le \text{total\_budget} \le \sum \text{max\_spend}_c$$
- [ ] For multidimensional/panel models: exact dimension coverage is specified

---

## When to Use

- User asks for optimal spend distribution across advertising channels for a given budget
- User wants to evaluate "what-if" counterfactual scenarios (e.g. $+30\%$ Meta, $-50\%$ TV)
- User asks to build a multi-week campaign flighting schedule (pulsed, frontloaded, flat)
- User wants to maximize net profit given gross margins and channel constraints
- User wants to find the spend level where a channel reaches marginal iROAS $= 1.0$

## When NOT to Use

- Model is rejected by MCMC diagnostics (`divergences > 0` or $\hat{R} > 1.05$) → use `pymc-diagnostics-gate`
- Initial dataset inspection, validation, and fitting → use `pymc-mmm-workflow`
- Calibrating model priors with geo-experiment lift tests → use `pymc-lift-calibration`

---

## The Decision Gate Prerequisite

Decision-grade optimization tools (`optimize_budget`, `optimize_flighting`, `simulate_budget`, `get_incremental_roas`) require a diagnostic approval. If `diagnose_mmm` returned `rejected`, the tools fail closed.

```text
               ┌─────────────────────────────────┐
               │    get_model_status(model_id)   │
               └────────────────┬────────────────┘
                                │
               ┌────────────────┴────────────────┐
               ▼                                 ▼
      [Approved / Caution]                  [Rejected]
      Proceed to Optimization               STOP. Route to
      (Keep warnings visible)               pymc-diagnostics-gate
```

---

## Procedure

### Step 1: Verify Gate Status
1. **Step:** Verify model decision readiness:
   Call `get_model_status(model_id=model_id)`.
   - **Key point:** Check that `decision_status` is `approved` or `approved_with_caution`.
   - **Why:** Prevents runtime rejection errors and ensures optimization is backed by clean posterior distributions.

### Step 2: Choose Decision Tool Archetype

| Business Intent | MCP Tool | Primary Arguments |
|---|---|---|
| **Find Mathematical Optimal Mix** | `optimize_budget` | `model_id`, `budget`, `planning_periods`, `constraints` |
| **Evaluate Specific User Proposal** | `simulate_budget` | `model_id`, `planning_periods`, `changes` |
| **Build Multi-Week Spend Schedule** | `optimize_flighting` | `model_id`, `total_budget`, `planning_weeks`, `channel_constraints` |
| **Check Marginal Productivity** | `get_incremental_roas` | `model_id` |

### Step 3: Run Constrained Budget Optimization
1. **Step:** Formulate and call `optimize_budget`:
   ```json
   {
     "model_id": "mmm_approved_v1",
     "budget": 500000.0,
     "planning_periods": 12,
     "constraints": {
       "meta_spend": {"min": 100000.0, "max": 250000.0},
       "search_spend": {"min": 150000.0, "max": 300000.0},
       "tv_spend": {"min": 50000.0, "max": 100000.0}
     }
   }
   ```
   - **Key point:** Sequential Least Squares Programming (SLSQP) solves for equal marginal returns across unconstrained channels.
   - **Why:** Allocating spend based on historical total ROAS over-invests in saturated channels; marginal returns guarantee maximum incremental return.
   - → Mathematical derivations: `references/optimization-math.md`
   - → Configuration template: `templates/optimize-budget-input.json`

### Step 4: Run Counterfactual Scenario Simulation
1. **Step:** When a user asks "what happens if we cut TV spend by 50% and move it to Meta?", call `simulate_budget`:
   ```json
   {
     "model_id": "mmm_approved_v1",
     "planning_periods": 8,
     "changes": {
       "tv_spend": {"type": "relative", "value": -0.50},
       "meta_spend": {"type": "absolute", "value": 250000.0}
     }
   }
   ```
   - **Key point:** Evaluate the *exact scenario requested*. Never substitute optimizer output for a user's counterfactual query.
   - **Why:** The stakeholder wants to understand the performance delta of their specific strategic proposal.
   - → Scenario template: `templates/simulate-scenario-input.json`

### Step 5: Construct Dynamic Media Flighting
1. **Step:** For multi-week temporal allocation accounting for carryover and adstock decay, call `optimize_flighting`:
   ```json
   {
     "model_id": "mmm_approved_v1",
     "total_budget": 1200000.0,
     "planning_weeks": 12,
     "objective": "maximize_net_profit",
     "margin_pct": 0.40,
     "channel_constraints": [
       {"channel": "tv_spend", "pattern": "pulsed", "min_weekly": 10000.0, "max_weekly": 80000.0},
       {"channel": "meta_spend", "pattern": "frontloaded", "min_weekly": 20000.0, "max_weekly": 60000.0}
     ]
   }
   ```
   - **Key point:** Pulsing exploits high TV adstock decay to maintain continuous brand awareness with intermittent spend.
   - → Flighting strategies guide: `references/flighting-strategies.md`

### Step 6: Interpret Results & Handle Warnings
1. **Step:** Check for Extrapolation Warnings:
   - If proposed spend exceeds $1.5\times$ the historical 95th percentile spend, flag `EXTRAPOLATION_RISK`.
   - Explain that response curve estimates at that volume have wider uncertainty.
2. **Step:** Report expected incremental KPI lift alongside 94% HDI credible intervals.
   - → Full walkthrough example: `examples/q4-budget-reallocation-walkthrough.md`

---

## Common Mistakes & Mitigations

| Mistake | Signal | Mitigation |
|---|---|---|
| **Substituting Optimizer for Simulation** | User asks "what if we do X?" $\to$ agent returns `optimize_budget` | Use `simulate_budget` to test their proposal; then optionally compare to optimal. |
| **Omitting Channel Constraints** | Unconstrained optimization allocating $90\%$ to one channel | Always set operational `min` and `max` constraints to prevent channel starvation. |
| **Ignoring Infeasible Constraints** | Min constraints sum to $\$600k$ with a $\$500k$ budget | Catch infeasibility before running; alert user to adjust bounds. |
| **Suppressing Extrapolation Risk** | Hiding extrapolation warnings to make projections look certain | Always disclose extrapolation warnings when spend moves beyond observed support. |

---

## Decision Rules

- Never execute optimization on a model with `decision_status: "rejected"`.
- Honor exact total budget and explicit channel constraints; report infeasible constraints rather than silently relaxing them.
- Always report posterior uncertainty (94% HDI) on projected revenue and profit lift.
- In multidimensional/panel optimization, require exact cell coverage; ambiguous aggregate bounds must fail closed.

---

## Neural Connections

- **Upstream Precursors:** `pymc-mmm-workflow`, `pymc-diagnostics-gate`
- **Downstream Continuations:** `pymc-lift-calibration`
- **Lateral Peers:** `pymc-clv-customer-analytics`
- **Recovery Handler:** `pymc-diagnostics-gate`
